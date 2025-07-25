import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import openai
import datetime
from datetime import date, timedelta
import random
import math
import json
from sqlalchemy import func, text

# --- Configuration ---
app = Flask(__name__)
CORS(app)

# Configuration for PostgreSQL and sessions
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///life_rpg.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Handle Railway PostgreSQL URL format
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your Life RPG.'

# --- Constants ---
ATTRIBUTES = {
    "Strength": ["Lifting", "Athletics", "Physical Labor", "Martial Arts", "Power"],
    "Dexterity": ["Coordination", "Agility", "Balance", "Speed", "Reflexes"],
    "Constitution": ["Endurance", "Health", "Vitality", "Recovery", "Resistance"],
    "Intelligence": ["Learning", "Problem-Solving", "Memory", "Analysis", "Technical Skills"],
    "Wisdom": ["Insight", "Intuition", "Perception", "Self-Awareness", "Decision-Making"],
    "Charisma": ["Communication", "Leadership", "Persuasion", "Social Skills", "Influence"]
}
QUEST_DIFFICULTIES = ["Easy", "Medium", "Hard", "Epic"]
TASK_DIFFICULTIES = {"easy": 10, "medium": 25, "hard": 50, "extra_hard": 100}

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationships (one-to-many unless specified)
    attributes = db.relationship('Attribute', backref='user', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='user', lazy=True, cascade='all, delete-orphan')
    quests = db.relationship('Quest', backref='user', lazy=True, cascade='all, delete-orphan')
    milestones = db.relationship('Milestone', backref='user', lazy=True, cascade='all, delete-orphan')
    narratives = db.relationship('DailyNarrative', backref='user', lazy=True, cascade='all, delete-orphan')
    recurring_tasks = db.relationship('RecurringTask', backref='user', lazy=True, cascade='all, delete-orphan')
    daily_stats = db.relationship('DailyStat', backref='user', lazy=True, cascade='all, delete-orphan')
    character_stats = db.relationship('CharacterStat', backref='user', lazy=True, cascade='all, delete-orphan')
    narrative_progress = db.relationship('NarrativeProgress', backref='user', uselist=False, cascade='all, delete-orphan')

    # NEW: Relationships for new features
    credo = db.relationship('Credo', backref='user', uselist=False, cascade='all, delete-orphan')
    notes = db.relationship('Note', backref='user', lazy=True, cascade='all, delete-orphan')
    daily_checklist_items = db.relationship('DailyChecklistItem', backref='user', lazy=True, cascade='all, delete-orphan')
    daily_checklist_logs = db.relationship('DailyChecklistLog', backref='user', lazy=True, cascade='all, delete-orphan')

class Attribute(db.Model):
    attribute_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)  # ADDED: Missing description field
    current_xp = db.Column(db.Integer, default=0)
    
    # Relationship to subskills
    subskills = db.relationship('Subskill', backref='attribute', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'name'),)

# NEW: Missing Subskill model
class Subskill(db.Model):
    subskill_id = db.Column(db.Integer, primary_key=True)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.attribute_id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    current_xp = db.Column(db.Integer, default=0)
    
    __table_args__ = (db.UniqueConstraint('attribute_id', 'name'),)

class Task(db.Model):
    task_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    description = db.Column(db.Text, nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.attribute_id'))
    subskill_id = db.Column(db.Integer, db.ForeignKey('subskill.subskill_id'))  # ADDED: Missing subskill_id
    xp_gained = db.Column(db.Integer, default=0)
    is_completed = db.Column(db.Boolean, default=False)
    is_skipped = db.Column(db.Boolean, default=False)
    is_negative_habit = db.Column(db.Boolean, default=False)
    
    # ADDED: Missing fields
    task_type = db.Column(db.String(20), default='general')
    stress_effect = db.Column(db.Integer, default=0)
    numeric_value = db.Column(db.Float, nullable=True)
    numeric_unit = db.Column(db.String(50), nullable=True)
    logged_numeric_value = db.Column(db.Float, nullable=True)
    negative_habit_done = db.Column(db.Boolean, default=None)  # ADDED: For negative habit tracking
    
    # Relationships
    attribute = db.relationship('Attribute', backref='tasks')
    subskill = db.relationship('Subskill', backref='tasks')
        
class Quest(db.Model):
    quest_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='Active')
    
    # ADDED: Missing fields
    difficulty = db.Column(db.String(20), default='Medium')
    xp_reward = db.Column(db.Integer, default=100)
    attribute_focus = db.Column(db.String(50))
    start_date = db.Column(db.String(10))
    due_date = db.Column(db.String(10))
    completed_date = db.Column(db.String(10))
    
    steps = db.relationship('QuestStep', backref='quest', lazy='dynamic', cascade='all, delete-orphan')

class QuestStep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quest_id = db.Column(db.Integer, db.ForeignKey('quest.quest_id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    is_completed = db.Column(db.Boolean, default=False)

# NEW: Missing NarrativeProgress model
class NarrativeProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    story_day = db.Column(db.Integer, default=1)
    current_location = db.Column(db.String(200), default='The Crossroads Inn')
    main_quest = db.Column(db.Text, default='Seeking your destiny as an adventurer')
    companions = db.Column(db.Text, default='None yet')
    recent_events = db.Column(db.Text, default='Beginning of your journey')
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# --- NEW MODELS ---
class Credo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    content = db.Column(db.Text, default="Define your core principles, your 'why'. What guides your journey?")
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class DailyChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class DailyChecklistLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('daily_checklist_item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # e.g., 'completed', 'missed'
    item = db.relationship('DailyChecklistItem')
    __table_args__ = (db.UniqueConstraint('item_id', 'date', 'user_id'),)

class Milestone(db.Model):
    milestone_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.attribute_id'))
    achievement_type = db.Column(db.String(50), nullable=False)
    
    # Relationship to access attribute object
    attribute = db.relationship('Attribute', backref='milestones')

class DailyNarrative(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    narrative = db.Column(db.Text, nullable=False)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'date'),)

class RecurringTask(db.Model):
    recurring_task_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.attribute_id'))
    subskill_id = db.Column(db.Integer, db.ForeignKey('subskill.subskill_id'))
    xp_value = db.Column(db.Integer, default=0)
    stress_effect = db.Column(db.Integer, default=0)
    is_negative_habit = db.Column(db.Boolean, default=False)
    start_date = db.Column(db.String(10), nullable=False)
    last_added_date = db.Column(db.String(10))
    is_active = db.Column(db.Boolean, default=True)
    # --- NEW FIELDS FOR NUMERIC TRACKING ---
    numeric_value = db.Column(db.Float, nullable=True)
    numeric_unit = db.Column(db.String(50), nullable=True)
    
    # Relationships to access attribute and subskill objects
    attribute = db.relationship('Attribute', backref='recurring_tasks')
    subskill = db.relationship('Subskill', backref='recurring_tasks')

class DailyStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    stress_level = db.Column(db.Integer, default=0)
    tasks_completed = db.Column(db.Integer, default=0)
    total_xp_gained = db.Column(db.Integer, default=0)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'date'),)

class CharacterStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stat_name = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Integer, default=0)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'stat_name'),)

# --- Login Manager ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Helper Functions ---
def calculate_exp_for_level(level):
    if level <= 1: return 0
    return int(100 * (level - 1) ** 2.2)

def calculate_level_from_exp(exp):
    if exp is None or exp <= 0: return 1
    return int(1 + (exp / 100) ** (1/2.2))

def generate_ai_response(prompt, system_message, api_key):
    """Generate AI response using user's API key"""
    try:
        openai.api_key = api_key
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error with AI generation: {e}")
        return f"AI Error: {str(e)}"

def initialize_user_data(user):
    """Initialize default attributes and stats for a new user"""
    # Create default attributes
    for attr_name, sub_list in ATTRIBUTES.items():
        attribute = Attribute(
            user_id=user.id,
            name=attr_name,
            description=f"Your {attr_name} attribute",
            current_xp=0
        )
        db.session.add(attribute)
        db.session.flush()  # Get the ID
        
        # Create subskills
        for sub_name in sub_list:
            subskill = Subskill(
                attribute_id=attribute.attribute_id,
                name=sub_name,
                current_xp=0
            )
            db.session.add(subskill)

    # Create narrative progress
    narrative_progress = NarrativeProgress(user_id=user.id)
    db.session.add(narrative_progress)
    
    # Create default credo
    credo = Credo(user_id=user.id)
    db.session.add(credo)
    
    db.session.commit()
    
    # Create default character stats
    stress_stat = CharacterStat(
        user_id=user.id,
        stat_name='Stress',
        value=0
    )
    db.session.add(stress_stat)
    
    db.session.commit()

# --- Authentication Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # Validation
        if not username or not email or not password:
            if request.is_json:
                return jsonify({'success': False, 'error': 'All fields are required'}), 400
            flash('All fields are required')
            return render_template('register.html')
        
        # Check if user exists
        if User.query.filter((User.username == username) | (User.email == email)).first():
            if request.is_json:
                return jsonify({'success': False, 'error': 'Username or email already exists'}), 400
            flash('Username or email already exists')
            return render_template('register.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        # Initialize user data
        initialize_user_data(user)
        
        # Log them in
        login_user(user)
        
        if request.is_json:
            return jsonify({'success': True, 'redirect': '/'})
        
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            if request.is_json:
                return jsonify({'success': True, 'redirect': '/'})
            return redirect(url_for('index'))
        
        if request.is_json:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        flash('Invalid username/email or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- Main Routes ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

@app.route('/api/test_api_key', methods=['POST'])
@login_required
def test_api_key():
    """Test if the provided API key is valid"""
    data = request.json
    api_key = data.get('api_key')
    
    if not api_key:
        return jsonify({'success': False, 'error': 'No API key provided'})
    
    try:
        openai.api_key = api_key
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        return jsonify({'success': True})
    except Exception as e:
        error_message = str(e)
        print(f"API key test failed: {error_message}")
        return jsonify({'success': False, 'error': error_message})

# --- API Routes ---
@app.route('/api/attributes')
@login_required
def api_get_attributes():
    attributes = Attribute.query.filter_by(user_id=current_user.id).order_by(Attribute.name).all()
    
    attributes_data = []
    for attr in attributes:
        level = calculate_level_from_exp(attr.current_xp)
        current_level_xp = calculate_exp_for_level(level)
        next_level_xp = calculate_exp_for_level(level + 1)
        xp_progress = attr.current_xp - current_level_xp
        xp_needed = next_level_xp - current_level_xp
        progress_percent = (xp_progress / xp_needed * 100) if xp_needed > 0 else 100
        
        # Get subskills
        subskills_data = []
        for subskill in attr.subskills:
            sub_level = calculate_level_from_exp(subskill.current_xp)
            sub_current_level_xp = calculate_exp_for_level(sub_level)
            sub_next_level_xp = calculate_exp_for_level(sub_level + 1)
            sub_xp_progress = subskill.current_xp - sub_current_level_xp
            sub_xp_needed = sub_next_level_xp - sub_current_level_xp
            sub_progress_percent = (sub_xp_progress / sub_xp_needed * 100) if sub_xp_needed > 0 else 100
            
            subskills_data.append({
                'id': subskill.subskill_id,
                'name': subskill.name,
                'level': sub_level,
                'total_xp': subskill.current_xp,
                'xp_progress': sub_xp_progress,
                'xp_needed': sub_xp_needed,
                'progress_percent': sub_progress_percent
            })
        
        attributes_data.append({
            'id': attr.attribute_id,
            'name': attr.name,
            'level': level,
            'total_xp': attr.current_xp,
            'xp_progress': xp_progress,
            'xp_needed': xp_needed,
            'progress_percent': progress_percent,
            'subskills': subskills_data
        })
    
    return jsonify(attributes_data)

@app.route('/api/tasks')
@login_required
def api_get_tasks():
    date = request.args.get('date', datetime.date.today().isoformat())
    
    # Process recurring tasks for this date
    recurring_tasks = RecurringTask.query.filter_by(
        user_id=current_user.id, 
        is_active=True
    ).filter(RecurringTask.start_date <= date).all()
    
    for rt in recurring_tasks:
        # Check if already added for this date
        existing_task = Task.query.filter_by(
            user_id=current_user.id,
            date=date,
            description=rt.description
        ).first()
        
        if not existing_task:
            task = Task(
                user_id=current_user.id,
                date=date,
                description=rt.description,
                task_type='recurring',
                attribute_id=rt.attribute_id,
                subskill_id=rt.subskill_id,
                xp_gained=rt.xp_value,
                stress_effect=rt.stress_effect,
                is_negative_habit=rt.is_negative_habit,
                numeric_value=rt.numeric_value,
                numeric_unit=rt.numeric_unit
            )
            db.session.add(task)
    
    db.session.commit()
    
    # Get tasks for the date, sorted alphabetically
    tasks = Task.query.filter_by(user_id=current_user.id, date=date).order_by(
        Task.is_completed, Task.is_skipped, Task.description.asc()
    ).all()
    
    tasks_data = []
    for task in tasks:
        tasks_data.append({
            'id': task.task_id,
            'description': task.description,
            'type': task.task_type,
            'completed': task.is_completed,
            'skipped': task.is_skipped,
            'attribute': task.attribute.name if task.attribute else None,
            'subskill': task.subskill.name if task.subskill else None,
            'xp': task.xp_gained,
            'stress_effect': task.stress_effect,
            'is_negative_habit': task.is_negative_habit,
            'numeric_value': task.numeric_value,
            'numeric_unit': task.numeric_unit,
            'logged_numeric_value': task.logged_numeric_value
        })
    
    return jsonify(tasks_data)

@app.route('/api/add_task', methods=['POST'])
@login_required
def api_add_task():
    data = request.json
    
    # Get attribute and subskill
    attribute = None
    subskill = None
    
    if data.get('attribute'):
        attribute = Attribute.query.filter_by(
            user_id=current_user.id, 
            name=data['attribute']
        ).first()
        
        if attribute and data.get('subskill'):
            subskill = Subskill.query.filter_by(
                attribute_id=attribute.attribute_id,
                name=data['subskill']
            ).first()
    
    # Calculate XP based on difficulty
    xp = 0 if data.get('is_negative_habit') else TASK_DIFFICULTIES.get(data.get('difficulty', 'medium'), 25)
    
    # --- NEW: Automatically assign a unit for non-numeric negative habits ---
    is_negative = data.get('is_negative_habit', False)
    numeric_unit = data.get('numeric_unit') if data.get('numeric_unit') else None
    if is_negative and not numeric_unit:
        numeric_unit = 'occurrence'

    task = Task(
        user_id=current_user.id,
        date=data.get('date', datetime.date.today().isoformat()),
        description=data['description'],
        task_type=data.get('type', 'general'),
        attribute_id=attribute.attribute_id if attribute else None,
        subskill_id=subskill.subskill_id if subskill else None,
        xp_gained=xp,
        stress_effect=int(data.get('stress_effect', 0)),
        is_negative_habit=is_negative,
        numeric_value=data.get('numeric_value') if data.get('numeric_value') else None,
        numeric_unit=numeric_unit
    )
    
    db.session.add(task)
    db.session.commit()
    
    return jsonify({'success': True, 'task_id': task.task_id})

@app.route('/api/complete_task', methods=['POST'])
@login_required
def api_complete_task():
    data = request.json
    task_id = data.get('task_id')
    logged_numeric_value = data.get('logged_numeric_value')

    task = Task.query.filter_by(task_id=task_id, user_id=current_user.id).first()
    if not task:
        return jsonify({'success': False, 'error': 'Task not found'})
    if task.is_completed:
        return jsonify({'success': False, 'error': 'Task already completed'})

    task.is_completed = True
    if logged_numeric_value is not None:
        try:
            task.logged_numeric_value = float(logged_numeric_value)
        except (ValueError, TypeError):
            pass

    is_success = False
    
    if task.is_negative_habit:
        goal = task.numeric_value if task.numeric_value is not None else 0
        if task.logged_numeric_value is not None and task.logged_numeric_value <= goal:
            is_success = True
        # Set the flag for stats tracking
        task.negative_habit_done = not is_success
    else:
        if task.numeric_unit is None:
            is_success = True
        elif task.logged_numeric_value is not None and task.logged_numeric_value > 0:
            is_success = True

    if is_success:
        reward_xp = task.xp_gained or 25
        
        if task.attribute:
            task.attribute.current_xp += reward_xp
        if task.subskill:
            task.subskill.current_xp += reward_xp
        
        if task.is_negative_habit:
            stress_stat = CharacterStat.query.filter_by(user_id=current_user.id, stat_name='Stress').first()
            if stress_stat:
                stress_stat.value = max(0, stress_stat.value - 5)
    else:
        if task.is_negative_habit:
            stress_stat = CharacterStat.query.filter_by(user_id=current_user.id, stat_name='Stress').first()
            if stress_stat and task.stress_effect != 0:
                stress_stat.value = max(0, stress_stat.value + abs(task.stress_effect))

    today = datetime.date.today().isoformat()
    daily_stat = DailyStat.query.filter_by(user_id=current_user.id, date=today).first()
    if not daily_stat:
        daily_stat = DailyStat(user_id=current_user.id, date=today, tasks_completed=0, total_xp_gained=0)
        db.session.add(daily_stat)

    if daily_stat.tasks_completed is None: daily_stat.tasks_completed = 0
    if daily_stat.total_xp_gained is None: daily_stat.total_xp_gained = 0

    if is_success:
        daily_stat.tasks_completed += 1
        daily_stat.total_xp_gained += (task.xp_gained or 25)

    db.session.commit()
    return jsonify({'success': True, 'was_success': is_success})

@app.route('/api/complete_negative_habit', methods=['POST'])
@login_required
def api_complete_negative_habit():
    data = request.json
    task_id = data.get('task_id')
    did_negative = data.get('did_negative')
    
    task = Task.query.filter_by(task_id=task_id, user_id=current_user.id).first()
    if not task or not task.is_negative_habit:
        return jsonify({'success': False, 'error': 'Invalid task'})
    
    if task.is_completed:
        return jsonify({'success': False, 'error': 'Task already completed'})
    
    task.is_completed = True
    task.negative_habit_done = did_negative
    
    if did_negative:
        if task.stress_effect != 0:
            stress_stat = CharacterStat.query.filter_by(
                user_id=current_user.id, 
                stat_name='Stress'
            ).first()
            if stress_stat:
                stress_stat.value = max(0, stress_stat.value + abs(task.stress_effect))
    else:
        reward_xp = task.xp_gained or 25
        if task.attribute:
            task.attribute.current_xp += reward_xp
        if task.subskill:
            task.subskill.current_xp += reward_xp
        
        stress_stat = CharacterStat.query.filter_by(
            user_id=current_user.id, 
            stat_name='Stress'
        ).first()
        if stress_stat:
            stress_stat.value = max(0, stress_stat.value - 5)
    
    today = datetime.date.today().isoformat()
    daily_stat = DailyStat.query.filter_by(user_id=current_user.id, date=today).first()
    if not daily_stat:
        daily_stat = DailyStat(
            user_id=current_user.id, 
            date=today,
            stress_level=0,
            tasks_completed=0,
            total_xp_gained=0
        )
        db.session.add(daily_stat)
    
    if daily_stat.tasks_completed is None:
        daily_stat.tasks_completed = 0
    if daily_stat.total_xp_gained is None:
        daily_stat.total_xp_gained = 0
    
    daily_stat.tasks_completed += 1
    if not did_negative:
        daily_stat.total_xp_gained += (task.xp_gained or 25)
    
    db.session.commit()
    return jsonify({'success': True, 'did_negative': did_negative})

@app.route('/api/skip_task', methods=['POST'])
@login_required
def api_skip_task():
    data = request.json
    task_id = data.get('task_id')
    
    task = Task.query.filter_by(task_id=task_id, user_id=current_user.id).first()
    if not task:
        return jsonify({'success': False, 'error': 'Task not found'})
    
    if task.is_completed or task.is_skipped:
        return jsonify({'success': False, 'error': 'Task already completed or skipped'})
    
    task.is_skipped = True
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/delete_task', methods=['POST'])
@login_required
def api_delete_task():
    data = request.json
    task_id = data.get('task_id')
    
    task = Task.query.filter_by(task_id=task_id, user_id=current_user.id).first()
    if not task:
        return jsonify({'success': False, 'error': 'Task not found'})
    
    if task.is_completed and not task.is_negative_habit and task.xp_gained > 0:
        if task.attribute:
            task.attribute.current_xp = max(0, task.attribute.current_xp - task.xp_gained)
        if task.subskill:
            task.subskill.current_xp = max(0, task.subskill.current_xp - task.xp_gained)
    
    db.session.delete(task)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/stats')
@login_required
def api_get_stats():
    stats = {}
    
    character_stats = CharacterStat.query.filter_by(user_id=current_user.id).all()
    for stat in character_stats:
        stats[stat.stat_name] = stat.value
    
    stats['Total Tasks Completed'] = Task.query.filter_by(
        user_id=current_user.id, 
        is_completed=True
    ).count()
    
    stats['Negative Habits Done'] = Task.query.filter_by(
        user_id=current_user.id, 
        is_completed=True, 
        is_negative_habit=True,
        negative_habit_done=True
    ).count()
    
    stats['Negative Habits Avoided'] = Task.query.filter_by(
        user_id=current_user.id, 
        is_completed=True, 
        is_negative_habit=True,
        negative_habit_done=False
    ).count()
    
    today = datetime.date.today().isoformat()
    stats['Tasks Skipped Today'] = Task.query.filter_by(
        user_id=current_user.id, 
        date=today, 
        is_skipped=True
    ).count()
    
    stats['Tasks Remaining Today'] = Task.query.filter_by(
        user_id=current_user.id, 
        date=today, 
        is_completed=False, 
        is_skipped=False
    ).count()
    
    total_xp = db.session.query(db.func.sum(Attribute.current_xp)).filter_by(user_id=current_user.id).scalar()
    stats['Total XP'] = total_xp or 0
    
    stats['Active Quests'] = Quest.query.filter_by(
        user_id=current_user.id, 
        status='Active'
    ).count()
    
    stats['Completed Quests'] = Quest.query.filter_by(
        user_id=current_user.id, 
        status='Completed'
    ).count()
    
    return jsonify(stats)

@app.route('/api/milestones')
@login_required
def api_get_milestones():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    
    total = Milestone.query.filter_by(user_id=current_user.id).count()
    
    milestones = Milestone.query.filter_by(user_id=current_user.id).order_by(
        Milestone.date.desc(), Milestone.milestone_id.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    milestones_data = []
    for milestone in milestones.items:
        milestones_data.append({
            'id': milestone.milestone_id,
            'date': milestone.date,
            'title': milestone.title,
            'description': milestone.description,
            'type': milestone.achievement_type,
            'attribute': milestone.attribute.name if milestone.attribute else None
        })
    
    return jsonify({
        'milestones': milestones_data,
        'current_page': page,
        'pages': milestones.pages,
        'total': total
    })

@app.route('/api/delete_milestone', methods=['POST'])
@login_required
def api_delete_milestone():
    data = request.json
    milestone_id = data.get('milestone_id')
    
    milestone = Milestone.query.filter_by(
        milestone_id=milestone_id, 
        user_id=current_user.id
    ).first()
    
    if milestone:
        db.session.delete(milestone)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Milestone not found'})

@app.route('/api/narrative')
@login_required
def api_get_narrative():
    date = request.args.get('date', datetime.date.today().isoformat())
    
    narrative = DailyNarrative.query.filter_by(
        user_id=current_user.id, 
        date=date
    ).first()
    
    narrative_text = narrative.narrative if narrative else "No adventure recorded for this day yet..."
    
    return jsonify({
        'date': date,
        'narrative': narrative_text
    })

@app.route('/api/generate_narrative', methods=['POST'])
@login_required
def api_generate_narrative():
    data = request.json
    api_key = data.get('api_key')
    date = data.get('date', datetime.date.today().isoformat())
    
    if not api_key:
        return jsonify({'error': 'API key required'}), 400
    
    progress = NarrativeProgress.query.filter_by(user_id=current_user.id).first()
    if not progress:
        progress = NarrativeProgress(user_id=current_user.id)
        db.session.add(progress)
        db.session.flush()
    
    last_narrative = DailyNarrative.query.filter_by(user_id=current_user.id).order_by(
        DailyNarrative.date.desc()
    ).first()
    
    context = f"""
Current Story State:
- Location: {progress.current_location}
- Main Quest: {progress.main_quest}
- Companions: {progress.companions}
- Recent Events: {progress.recent_events}
- Story Day: {progress.story_day}
"""
    
    if last_narrative:
        context += f"\nYesterday's Events: {last_narrative.narrative}"
    
    story_info = get_story_phase_and_focus(progress.story_day)
    
    prompt = f"""Write today's D&D adventure entry for an ongoing epic story. 

STORY PROGRESSION:
- Overall Day: {progress.story_day}
- Chapter: {story_info['chapter']} 
- Day in Chapter: {story_info['day_in_chapter']}
- Phase: {story_info['phase']}
- Power Level: {story_info['complexity']}

{context}

WRITING GUIDELINES:
- {story_info['focus']}
- {story_info['scope']}
- Advance the story meaningfully - no repetition or circular events
- Include specific details: names, places, discoveries, or encounters
- Show character growth and escalating power/responsibility
- Keep it engaging and around 120-150 words
- End with a hook for tomorrow

SPECIAL INSTRUCTIONS:
{get_special_chapter_instructions(story_info['day_in_chapter'], story_info['chapter'])}

At the end, update the story state in this format:
[LOCATION: new location if changed]
[QUEST: updated main quest if evolved]
[COMPANIONS: current companions]
[EVENTS: summary of today's key events]"""
    
    system_message = """You are a master D&D dungeon master creating a continuous, evolving epic saga. Each day should meaningfully advance the narrative with proper story structure. Create memorable moments that build toward greater adventures. Avoid repetition and ensure real progression through escalating challenges and character growth."""
    
    narrative_text = generate_ai_response(prompt, system_message, api_key)
    
    lines = narrative_text.split('\n')
    story_updates = {}
    clean_narrative = []
    
    for line in lines:
        if line.startswith('[LOCATION:'):
            story_updates['location'] = line.replace('[LOCATION:', '').replace(']', '').strip()
        elif line.startswith('[QUEST:'):
            story_updates['quest'] = line.replace('[QUEST:', '').replace(']', '').strip()
        elif line.startswith('[COMPANIONS:'):
            story_updates['companions'] = line.replace('[COMPANIONS:', '').replace(']', '').strip()
        elif line.startswith('[EVENTS:'):
            story_updates['events'] = line.replace('[EVENTS:', '').replace(']', '').strip()
        else:
            clean_narrative.append(line)
    
    final_narrative = '\n'.join(clean_narrative).strip()
    
    if story_updates.get('location'):
        progress.current_location = story_updates['location']
    if story_updates.get('quest'):
        progress.main_quest = story_updates['quest']
    if story_updates.get('companions'):
        progress.companions = story_updates['companions']
    if story_updates.get('events'):
        progress.recent_events = story_updates['events']
    
    progress.story_day += 1
    progress.updated_at = datetime.datetime.utcnow()
    
    existing_narrative = DailyNarrative.query.filter_by(
        user_id=current_user.id, 
        date=date
    ).first()
    
    if existing_narrative:
        existing_narrative.narrative = final_narrative
    else:
        new_narrative = DailyNarrative(
            user_id=current_user.id,
            date=date,
            narrative=final_narrative
        )
        db.session.add(new_narrative)
    
    db.session.commit()
    
    return jsonify({
        'narrative': final_narrative, 
        'date': date,
        'story_day': progress.story_day - 1,
        'location': progress.current_location,
        'quest': progress.main_quest,
        'chapter': story_info['chapter'],
        'phase': story_info['phase'],
        'complexity': story_info['complexity']
    })

def get_story_phase_and_focus(story_day):
    chapter = (story_day - 1) // 50 + 1
    day_in_chapter = ((story_day - 1) % 50) + 1
    
    if day_in_chapter <= 10:
        phase = "Opening"
        if chapter == 1:
            focus = "Begin your legendary journey. Introduce the world and initial quest."
        else:
            focus = f"Chapter {chapter} begins! New lands, new challenges, and greater threats emerge."
    
    elif day_in_chapter <= 25:
        phase = "Rising Action"
        focus = "Develop the main plot. Introduce allies, enemies, mysteries, and mounting challenges."
    
    elif day_in_chapter <= 40:
        phase = "Climax Building"
        focus = "Major conflicts intensify. Face significant trials, make crucial decisions, prepare for the climax."
    
    elif day_in_chapter <= 45:
        phase = "Climax"
        focus = "The chapter's main conflict reaches its peak! Epic battles, major revelations, heroic moments."
    
    else:
        phase = "Resolution"
        focus = "Conclude the chapter's main arc. Celebrate victories, mourn losses, set up the next adventure."
    
    if story_day <= 50:
        complexity = "Local Hero"
        scope = "Focus on personal growth and local threats."
    elif story_day <= 100:
        complexity = "Regional Champion" 
        scope = "Expand to affect kingdoms, face greater magical threats."
    elif story_day <= 200:
        complexity = "Continental Legend"
        scope = "Multi-kingdom politics, ancient evils, world-shaking events."
    else:
        complexity = "Mythic Figure"
        scope = "Godlike powers, planar threats, reality-altering consequences."
    
    return {
        'chapter': chapter,
        'day_in_chapter': day_in_chapter,
        'phase': phase,
        'focus': focus,
        'complexity': complexity,
        'scope': scope
    }

def get_special_chapter_instructions(day_in_chapter, chapter_num):
    if day_in_chapter == 1 and chapter_num > 1:
        return f"CHAPTER {chapter_num} OPENING: Introduce new setting, escalated threats, and evolved character status."
    
    elif day_in_chapter == 50:
        return "CHAPTER FINALE: Provide satisfying conclusion to this chapter's main arc. Hint at future adventures."
    
    elif day_in_chapter in [45, 46, 47, 48, 49]:
        return "CLIMAX SEQUENCE: This is peak drama! Make it epic and consequential."
    
    elif chapter_num >= 3 and day_in_chapter == 25:
        return "MID-CHAPTER TWIST: Introduce a major plot twist or revelation that changes everything."
    
    else:
        return "Continue the natural story progression."

@app.route('/api/narratives')
@login_required
def api_get_narratives():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 3, type=int)
    
    total = DailyNarrative.query.filter_by(user_id=current_user.id).count()
    
    narratives = DailyNarrative.query.filter_by(user_id=current_user.id).order_by(
        DailyNarrative.date.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    narratives_data = []
    for narrative in narratives.items:
        narratives_data.append({
            'date': narrative.date,
            'narrative': narrative.narrative
        })
    
    return jsonify({
        'narratives': narratives_data,
        'current_page': page,
        'pages': narratives.pages,
        'total': total
    })

@app.route('/api/heatmap')
@login_required
def api_get_heatmap():
    year = request.args.get('year', datetime.date.today().year, type=int)
    month = request.args.get('month', datetime.date.today().month, type=int)
    
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
    daily_stats = DailyStat.query.filter_by(user_id=current_user.id).filter(
        DailyStat.date >= start_date,
        DailyStat.date < end_date
    ).all()
    
    data = []
    for stat in daily_stats:
        data.append({
            'date': stat.date,
            'count': stat.tasks_completed,
            'xp': stat.total_xp_gained
        })
    
    return jsonify(data)

@app.route('/api/attribute_history')
@login_required
def api_get_attribute_history():
    days = request.args.get('days', 30, type=int)
    
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    
    user_attributes = Attribute.query.filter_by(user_id=current_user.id).all()
    
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.isoformat())
        current_date += datetime.timedelta(days=1)
    
    result = {
        'dates': dates,
        'attributes': {}
    }
    
    for attribute in user_attributes:
        levels = []
        running_xp = 0
        
        for date_str in dates:
            daily_xp = db.session.query(db.func.sum(Task.xp_gained)).filter_by(
                user_id=current_user.id,
                attribute_id=attribute.attribute_id,
                date=date_str,
                is_completed=True,
                is_negative_habit=False
            ).scalar() or 0
            
            running_xp += daily_xp
            levels.append(calculate_level_from_exp(running_xp))
        
        result['attributes'][attribute.name] = levels
    
    return jsonify(result)

# --- NEW PROGRESS TRACKING ENDPOINTS ---
@app.route('/api/get_numeric_habits')
@login_required
def get_numeric_habits():
    """Returns a list of unique descriptions for numeric habits."""
    habits = db.session.query(Task.description).filter(
        Task.user_id == current_user.id,
        Task.numeric_unit.isnot(None)
    ).distinct().order_by(Task.description).all()
    
    habit_list = [h[0] for h in habits]
    return jsonify(habit_list)

@app.route('/api/habit_progress')
@login_required
def get_habit_progress():
    habit_description = request.args.get('description')
    if not habit_description:
        return jsonify({'error': 'Habit description is required'}), 400

    habit_info = RecurringTask.query.filter_by(user_id=current_user.id, description=habit_description).first()
    if not habit_info:
        habit_info = Task.query.filter_by(user_id=current_user.id, description=habit_description).first()
    
    is_negative = habit_info.is_negative_habit if habit_info else False
    unit = habit_info.numeric_unit if habit_info else ''

    today = date.today()
    
    start_of_this_week = today - timedelta(days=today.weekday())
    start_of_last_week = start_of_this_week - timedelta(days=7)
    
    def get_week_stats(start_date):
        end_date = start_date + timedelta(days=6)
        stats = db.session.query(
            func.sum(Task.logged_numeric_value),
            func.avg(Task.logged_numeric_value),
            func.count(Task.task_id)
        ).filter(
            Task.user_id == current_user.id,
            Task.description == habit_description,
            Task.is_completed == True,
            Task.logged_numeric_value.isnot(None),
            Task.date >= start_date.isoformat(),
            Task.date <= end_date.isoformat()
        ).first()
        return {'total': stats[0] or 0, 'avg': stats[1] or 0, 'entries': stats[2] or 0}

    this_week_stats = get_week_stats(start_of_this_week)
    last_week_stats = get_week_stats(start_of_last_week)

    start_of_this_month = today.replace(day=1)
    start_of_last_month = (start_of_this_month - timedelta(days=1)).replace(day=1)

    def get_month_stats(start_date):
        end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        stats = db.session.query(
            func.sum(Task.logged_numeric_value),
            func.avg(Task.logged_numeric_value),
            func.count(Task.task_id)
        ).filter(
            Task.user_id == current_user.id,
            Task.description == habit_description,
            Task.is_completed == True,
            Task.logged_numeric_value.isnot(None),
            Task.date >= start_date.isoformat(),
            Task.date <= end_date.isoformat()
        ).first()
        return {'total': stats[0] or 0, 'avg': stats[1] or 0, 'entries': stats[2] or 0}

    this_month_stats = get_month_stats(start_of_this_month)
    last_month_stats = get_month_stats(start_of_last_month)
    
    def calc_change(current, previous, is_negative_habit):
        if previous > 0:
            if is_negative_habit:
                return round(((previous - current) / previous) * 100, 1)
            else:
                return round(((current - previous) / previous) * 100, 1)
        elif current > 0:
            return 100 if not is_negative_habit else -100
        return 0

    return jsonify({
        'week': {
            'this_week': this_week_stats,
            'last_week': last_week_stats,
            'total_change': calc_change(this_week_stats['total'], last_week_stats['total'], is_negative),
            'avg_change': calc_change(this_week_stats['avg'], last_week_stats['avg'], is_negative)
        },
        'month': {
            'this_month': this_month_stats,
            'last_month': last_month_stats,
            'total_change': calc_change(this_month_stats['total'], last_month_stats['total'], is_negative),
            'avg_change': calc_change(this_month_stats['avg'], last_month_stats['avg'], is_negative)
        },
        'unit': unit,
        'is_negative': is_negative
    })

# --- QUESTS & QUEST STEPS API ---
@app.route('/api/quests')
@login_required
def api_get_quests():
    quests = Quest.query.filter_by(user_id=current_user.id).order_by(
        (Quest.status == 'Active').desc(),
        Quest.due_date.asc().nullslast(),
        Quest.start_date.desc()
    ).all()
    
    quests_data = []
    for quest in quests:
        steps_data = []
        # UPDATED: Eagerly load steps for each quest
        for step in quest.steps.order_by(QuestStep.id):
            steps_data.append({
                'id': step.id,
                'description': step.description,
                'is_completed': step.is_completed
            })

        quests_data.append({
            'id': quest.quest_id,
            'title': quest.title,
            'description': quest.description,
            'difficulty': quest.difficulty,
            'xp_reward': quest.xp_reward,
            'attribute_focus': quest.attribute_focus,
            'start_date': quest.start_date,
            'due_date': quest.due_date,
            'completed_date': quest.completed_date,
            'status': quest.status,
            'steps': steps_data  # NEW: Include steps in response
        })
    
    return jsonify(quests_data)

@app.route('/api/add_quest', methods=['POST'])
@login_required
def api_add_quest():
    data = request.json
    
    quest = Quest(
        user_id=current_user.id,
        title=data['title'],
        description=data.get('description', ''),
        difficulty=data.get('difficulty', 'Medium'),
        xp_reward=data.get('xp_reward', 100),
        attribute_focus=data.get('attribute_focus', ''),
        start_date=datetime.date.today().isoformat(),
        due_date=data.get('due_date')
    )
    
    db.session.add(quest)
    db.session.commit()
    
    return jsonify({'success': True, 'quest_id': quest.quest_id})

# NEW: Endpoint to edit a quest's details
@app.route('/api/quests/<int:quest_id>', methods=['PUT'])
@login_required
def update_quest(quest_id):
    quest = Quest.query.filter_by(quest_id=quest_id, user_id=current_user.id).first_or_404()
    data = request.json
    
    quest.title = data.get('title', quest.title)
    quest.description = data.get('description', quest.description)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Quest updated.'})


@app.route('/api/complete_quest', methods=['POST'])
@login_required
def api_complete_quest():
    data = request.json
    quest_id = data.get('quest_id')
    
    quest = Quest.query.filter_by(quest_id=quest_id, user_id=current_user.id).first()
    if not quest or quest.status == 'Completed':
        return jsonify({'success': False, 'error': 'Quest not found or already completed'})
    
    # NEW: Check if all steps are completed
    incomplete_steps = quest.steps.filter_by(is_completed=False).count()
    if incomplete_steps > 0:
        return jsonify({'success': False, 'error': f'Cannot complete quest. {incomplete_steps} steps remaining.'}), 400

    today = datetime.date.today().isoformat()
    quest.status = 'Completed'
    quest.completed_date = today
    
    if quest.attribute_focus:
        attribute = Attribute.query.filter_by(
            user_id=current_user.id,
            name=quest.attribute_focus
        ).first()
        if attribute:
            attribute.current_xp += quest.xp_reward
    
    milestone = Milestone(
        user_id=current_user.id,
        date=today,
        title=f"Quest Completed: {quest.title}",
        description=f"Successfully completed the quest '{quest.title}' and earned {quest.xp_reward} XP!",
        achievement_type='quest'
    )
    db.session.add(milestone)
    
    db.session.commit()
    
    return jsonify({'success': True})

# NEW: Endpoint to add a quest step
@app.route('/api/quests/<int:quest_id>/steps', methods=['POST'])
@login_required
def add_quest_step(quest_id):
    quest = Quest.query.filter_by(quest_id=quest_id, user_id=current_user.id).first_or_404()
    data = request.json
    description = data.get('description')

    if not description:
        return jsonify({'success': False, 'error': 'Step description cannot be empty'}), 400

    step = QuestStep(quest_id=quest.quest_id, description=description)
    db.session.add(step)
    db.session.commit()

    return jsonify({
        'success': True, 
        'step': {
            'id': step.id, 
            'description': step.description,
            'is_completed': step.is_completed
        }
    }), 201

# NEW: Endpoint to toggle a quest step's completion
@app.route('/api/quest_steps/<int:step_id>/toggle', methods=['PUT'])
@login_required
def toggle_quest_step(step_id):
    step = QuestStep.query.get_or_404(step_id)
    # Ensure the step belongs to a quest owned by the current user
    if step.quest.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Forbidden'}), 403

    step.is_completed = not step.is_completed
    db.session.commit()
    return jsonify({'success': True, 'is_completed': step.is_completed})

# NEW: Endpoint to delete a quest step
@app.route('/api/quest_steps/<int:step_id>', methods=['DELETE'])
@login_required
def delete_quest_step(step_id):
    step = QuestStep.query.get_or_404(step_id)
    if step.quest.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Forbidden'}), 403
    
    db.session.delete(step)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Step deleted.'})

@app.route('/api/generate_quest', methods=['POST'])
@login_required
def api_generate_quest():
    data = request.json
    api_key = data.get('api_key')
    
    if not api_key:
        return jsonify({'error': 'API key required'}), 400
    
    attribute = data.get('attribute_focus', random.choice(list(ATTRIBUTES.keys())))
    difficulty = data.get('difficulty', random.choice(QUEST_DIFFICULTIES))
    
    prompt = f"Create a self-improvement quest focusing on {attribute} with {difficulty} difficulty. Format as:\nTitle: [quest title]\nDescription: [50 word description of what to do]"
    
    response = generate_ai_response(prompt,
                                  "You are a quest master creating real-life self-improvement quests.",
                                  api_key)
    
    lines = response.split('\n')
    title = "New Quest"
    description = response
    
    for line in lines:
        if line.startswith('Title:'):
            title = line.replace('Title:', '').strip()
        elif line.startswith('Description:'):
            description = line.replace('Description:', '').strip()
    
    xp_rewards = {"Easy": 50, "Medium": 100, "Hard": 175, "Epic": 250}
    due_days = {"Easy": 3, "Medium": 7, "Hard": 14, "Epic": 21}
    
    due_date = (datetime.date.today() + datetime.timedelta(days=due_days.get(difficulty, 7))).isoformat()
    
    return jsonify({
        'title': title,
        'description': description,
        'difficulty': difficulty,
        'attribute_focus': attribute,
        'xp_reward': xp_rewards.get(difficulty, 100),
        'due_date': due_date
    })

@app.route('/api/enhance_quest_description', methods=['POST'])
@login_required
def api_enhance_quest_description():
    data = request.json
    api_key = data.get('api_key')
    description = data.get('description')
    
    if not api_key:
        return jsonify({'error': 'API key required'}), 400
    
    if not description:
        return jsonify({'error': 'Description required'}), 400
    
    prompt = f"""Transform this real-world goal into an epic fantasy quest description. Be creative and avoid generic openings like "Embark on" or "Journey to":

Real Goal: "{description}"

Create a unique, engaging fantasy version that captures the essence but feels like a legendary quest. Use varied language - consider openings like:
- "Seek the ancient..."
- "Master the forbidden art of..."
- "Forge your destiny by..."
- "Uncover the secrets of..."
- "Prove your worth through..."
- "Claim dominion over..."
- "Break the curse of..."

Keep it to one powerful sentence (15-25 words). Make it sound legendary and personal."""
    
    enhanced = generate_ai_response(prompt,
                                  "You are a master storyteller creating unique fantasy quest descriptions. Avoid repetitive language and generic fantasy tropes.",
                                  api_key)
    
    return jsonify({'enhanced_description': enhanced})

@app.route('/api/recurring_tasks', methods=['GET'])
@login_required
def api_get_recurring_tasks():
    recurring_tasks = RecurringTask.query.filter_by(user_id=current_user.id).order_by(
        RecurringTask.is_active.desc(), RecurringTask.description
    ).all()
    
    tasks_data = []
    for rt in recurring_tasks:
        tasks_data.append({
            'recurring_task_id': rt.recurring_task_id,
            'description': rt.description,
            'attribute_name': rt.attribute.name if rt.attribute else None,
            'subskill_name': rt.subskill.name if rt.subskill else None,
            'xp_value': rt.xp_value,
            'stress_effect': rt.stress_effect,
            'is_negative_habit': rt.is_negative_habit,
            'is_active': rt.is_active,
            'last_added_date': rt.last_added_date,
            'numeric_value': rt.numeric_value,
            'numeric_unit': rt.numeric_unit
        })
    
    return jsonify(tasks_data)

@app.route('/api/recurring_tasks', methods=['POST'])
@login_required
def api_add_recurring_task():
    data = request.json
    
    attribute = None
    if data.get('attribute'):
        attribute = Attribute.query.filter_by(
            user_id=current_user.id,
            name=data['attribute']
        ).first()
    
    xp = 0 if data.get('is_negative_habit') else TASK_DIFFICULTIES.get(data.get('difficulty', 'medium'), 25)

    is_negative = data.get('is_negative_habit', False)
    numeric_unit = data.get('numeric_unit') if data.get('numeric_unit') else None
    if is_negative and not numeric_unit:
        numeric_unit = 'occurrence'
    
    recurring_task = RecurringTask(
        user_id=current_user.id,
        description=data['description'],
        attribute_id=attribute.attribute_id if attribute else None,
        xp_value=xp,
        stress_effect=int(data.get('stress_effect', 0)),
        is_negative_habit=is_negative,
        start_date=datetime.date.today().isoformat(),
        numeric_value=data.get('numeric_value') if data.get('numeric_value') else None,
        numeric_unit=numeric_unit
    )
    
    db.session.add(recurring_task)
    db.session.commit()
    
    return jsonify({'success': True, 'recurring_task_id': recurring_task.recurring_task_id})

@app.route('/api/recurring_tasks/<int:rt_id>', methods=['DELETE'])
@login_required
def api_delete_recurring_task(rt_id):
    recurring_task = RecurringTask.query.filter_by(
        recurring_task_id=rt_id,
        user_id=current_user.id
    ).first()
    
    if recurring_task:
        db.session.delete(recurring_task)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Recurring task not found'})

@app.route('/api/recurring_tasks/<int:rt_id>/toggle_active', methods=['POST'])
@login_required
def api_toggle_recurring_task(rt_id):
    recurring_task = RecurringTask.query.filter_by(
        recurring_task_id=rt_id,
        user_id=current_user.id
    ).first()
    
    if not recurring_task:
        return jsonify({'success': False, 'error': 'Recurring task not found'})
    
    recurring_task.is_active = not recurring_task.is_active
    db.session.commit()
    
    return jsonify({'success': True, 'is_active': recurring_task.is_active})

@app.route('/api/reset_day', methods=['POST'])
@login_required
def api_reset_day():
    data = request.json
    date = data.get('date', datetime.date.today().isoformat())
    
    try:
        completed_tasks = Task.query.filter_by(
            user_id=current_user.id,
            date=date,
            is_completed=True,
            is_negative_habit=False
        ).all()
        
        for task in completed_tasks:
            if task.attribute and task.xp_gained > 0:
                task.attribute.current_xp = max(0, task.attribute.current_xp - task.xp_gained)
            if task.subskill and task.xp_gained > 0:
                task.subskill.current_xp = max(0, task.subskill.current_xp - task.xp_gained)
        
        tasks_to_delete = Task.query.filter_by(user_id=current_user.id, date=date).all()
        tasks_deleted = len(tasks_to_delete)
        for task in tasks_to_delete:
            db.session.delete(task)
        
        DailyStat.query.filter_by(user_id=current_user.id, date=date).delete()
        
        DailyNarrative.query.filter_by(user_id=current_user.id, date=date).delete()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'date': date,
            'tasks_deleted': tasks_deleted
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/add-negative-habit-column')
def add_negative_habit_column():
    """Add the new negative_habit_done column to existing tasks table"""
    try:
        with db.engine.connect() as connection:
            connection.execute(text('ALTER TABLE task ADD COLUMN negative_habit_done BOOLEAN DEFAULT NULL'))
            connection.commit()
        return "Successfully added negative_habit_done column to task table!"
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            return "Column already exists - no action needed!"
        return f"Error adding column: {str(e)}"

@app.route('/api/story_progress')
@login_required
def api_get_story_progress():
    """Get current story progression details"""
    progress = NarrativeProgress.query.filter_by(user_id=current_user.id).first()
    
    if not progress:
        return jsonify({
            'story_day': 1,
            'location': 'The Crossroads Inn',
            'main_quest': 'Seeking your destiny as an adventurer',
            'companions': 'None yet'
        })
    
    return jsonify({
        'story_day': progress.story_day,
        'location': progress.current_location,
        'main_quest': progress.main_quest,
        'companions': progress.companions,
        'recent_events': progress.recent_events
    })

@app.route('/api/credo', methods=['GET'])
@login_required
def get_credo():
    credo = Credo.query.filter_by(user_id=current_user.id).first()
    if not credo:
        # Create a default credo for the user if it doesn't exist
        credo = Credo(user_id=current_user.id)
        db.session.add(credo)
        db.session.commit()
    return jsonify({'content': credo.content})

@app.route('/api/credo', methods=['POST'])
@login_required
def update_credo():
    data = request.json
    credo = Credo.query.filter_by(user_id=current_user.id).first()
    if not credo:
        credo = Credo(user_id=current_user.id)
        db.session.add(credo)
    
    credo.content = data.get('content', credo.content)
    db.session.commit()
    return jsonify({'success': True, 'content': credo.content})

# --- NEW: NOTES API ---
@app.route('/api/notes', methods=['GET'])
@login_required
def get_notes():
    notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.updated_at.desc()).all()
    return jsonify([{
        'id': note.id,
        'title': note.title,
        'content': note.content,
        'updated_at': note.updated_at.strftime('%Y-%m-%d %H:%M')
    } for note in notes])

@app.route('/api/notes', methods=['POST'])
@login_required
def create_note():
    data = request.json
    if not data.get('title'):
        return jsonify({'success': False, 'error': 'Title is required'}), 400
    
    note = Note(
        user_id=current_user.id,
        title=data['title'],
        content=data.get('content', '')
    )
    db.session.add(note)
    db.session.commit()
    return jsonify({'success': True, 'id': note.id}), 201

@app.route('/api/notes/<int:note_id>', methods=['PUT'])
@login_required
def update_note(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    data = request.json
    note.title = data.get('title', note.title)
    note.content = data.get('content', note.content)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
@login_required
def delete_note(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    db.session.delete(note)
    db.session.commit()
    return jsonify({'success': True})

# --- NEW: DAILY CHECKLIST API ---
@app.route('/api/daily_checklist_items', methods=['GET'])
@login_required
def get_daily_checklist_items():
    items = DailyChecklistItem.query.filter_by(user_id=current_user.id, is_active=True).order_by(DailyChecklistItem.id).all()
    return jsonify([{'id': item.id, 'question': item.question} for item in items])

@app.route('/api/daily_checklist_items', methods=['POST'])
@login_required
def add_daily_checklist_item():
    data = request.json
    question = data.get('question')
    if not question:
        return jsonify({'success': False, 'error': 'Question cannot be empty'}), 400

    item = DailyChecklistItem(user_id=current_user.id, question=question)
    db.session.add(item)
    db.session.commit()
    return jsonify({'success': True, 'item': {'id': item.id, 'question': item.question}}), 201

@app.route('/api/daily_checklist_items/<int:item_id>', methods=['DELETE'])
@login_required
def delete_daily_checklist_item(item_id):
    item = DailyChecklistItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    # Also delete associated logs to keep DB clean
    DailyChecklistLog.query.filter_by(item_id=item_id, user_id=current_user.id).delete()
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/daily_checklist_logs', methods=['GET'])
@login_required
def get_daily_checklist_logs():
    date = request.args.get('date', datetime.date.today().isoformat())
    
    # Get all active items for the user
    items = DailyChecklistItem.query.filter_by(user_id=current_user.id, is_active=True).all()
    
    # Get all logs for that specific day
    logs = DailyChecklistLog.query.filter_by(user_id=current_user.id, date=date).all()
    logs_by_item_id = {log.item_id: log.status for log in logs}

    # Combine them
    checklist_data = []
    for item in items:
        checklist_data.append({
            'id': item.id,
            'question': item.question,
            'status': logs_by_item_id.get(item.id, None) # Status is null if not logged
        })
    
    return jsonify(checklist_data)

@app.route('/api/daily_checklist_logs', methods=['POST'])
@login_required
def log_daily_checklist_item():
    data = request.json
    item_id = data.get('item_id')
    date = data.get('date')
    status = data.get('status') # 'completed' or 'missed'

    if not all([item_id, date, status]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    # Ensure the item belongs to the user
    item = DailyChecklistItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify({'success': False, 'error': 'Item not found'}), 404

    log = DailyChecklistLog.query.filter_by(item_id=item_id, date=date, user_id=current_user.id).first()
    
    if log:
        # If user clicks the same button again, un-log it. Otherwise, update it.
        if log.status == status:
            db.session.delete(log)
        else:
            log.status = status
    else:
        log = DailyChecklistLog(item_id=item_id, user_id=current_user.id, date=date, status=status)
        db.session.add(log)
        
    db.session.commit()
    return jsonify({'success': True})


# Initialize database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
