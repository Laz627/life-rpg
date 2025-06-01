import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import openai
import datetime
import random
import math
import json

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
    
    # Relationships (one-to-many)
    attributes = db.relationship('Attribute', backref='user', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='user', lazy=True, cascade='all, delete-orphan')
    quests = db.relationship('Quest', backref='user', lazy=True, cascade='all, delete-orphan')
    milestones = db.relationship('Milestone', backref='user', lazy=True, cascade='all, delete-orphan')
    narratives = db.relationship('DailyNarrative', backref='user', lazy=True, cascade='all, delete-orphan')
    recurring_tasks = db.relationship('RecurringTask', backref='user', lazy=True, cascade='all, delete-orphan')
    daily_stats = db.relationship('DailyStat', backref='user', lazy=True, cascade='all, delete-orphan')
    character_stats = db.relationship('CharacterStat', backref='user', lazy=True, cascade='all, delete-orphan')

class Attribute(db.Model):
    attribute_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    current_xp = db.Column(db.Integer, default=0)
    
    # Relationships
    subskills = db.relationship('Subskill', backref='attribute', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='attribute', lazy=True)
    
    # Unique constraint per user
    __table_args__ = (db.UniqueConstraint('user_id', 'name'),)

class Subskill(db.Model):
    subskill_id = db.Column(db.Integer, primary_key=True)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.attribute_id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    current_xp = db.Column(db.Integer, default=0)
    
    # Relationships
    tasks = db.relationship('Task', backref='subskill', lazy=True)

class Task(db.Model):
    task_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    description = db.Column(db.Text, nullable=False)
    task_type = db.Column(db.String(20), nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.attribute_id'))
    subskill_id = db.Column(db.Integer, db.ForeignKey('subskill.subskill_id'))
    xp_gained = db.Column(db.Integer, default=0)
    stress_effect = db.Column(db.Integer, default=0)
    is_completed = db.Column(db.Boolean, default=False)
    is_skipped = db.Column(db.Boolean, default=False)
    is_negative_habit = db.Column(db.Boolean, default=False)
    negative_habit_done = db.Column(db.Boolean, default=None)  # None=not answered, True=did it, False=avoided


class Quest(db.Model):
    quest_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    difficulty = db.Column(db.String(20))
    xp_reward = db.Column(db.Integer)
    attribute_focus = db.Column(db.String(50))
    start_date = db.Column(db.String(10), nullable=False)
    due_date = db.Column(db.String(10))
    completed_date = db.Column(db.String(10))
    status = db.Column(db.String(20), default='Active')

class Milestone(db.Model):
    milestone_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.attribute_id'))
    achievement_type = db.Column(db.String(50), nullable=False)

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
                is_negative_habit=rt.is_negative_habit
            )
            db.session.add(task)
    
    db.session.commit()
    
    # Get tasks for the date
    tasks = Task.query.filter_by(user_id=current_user.id, date=date).order_by(
        Task.is_completed, Task.is_skipped, Task.task_id.desc()
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
            'is_negative_habit': task.is_negative_habit
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
    
    task = Task(
        user_id=current_user.id,
        date=data.get('date', datetime.date.today().isoformat()),
        description=data['description'],
        task_type=data.get('type', 'general'),
        attribute_id=attribute.attribute_id if attribute else None,
        subskill_id=subskill.subskill_id if subskill else None,
        xp_gained=xp,
        stress_effect=int(data.get('stress_effect', 0)),
        is_negative_habit=data.get('is_negative_habit', False)
    )
    
    db.session.add(task)
    db.session.commit()
    
    return jsonify({'success': True, 'task_id': task.task_id})

@app.route('/api/complete_task', methods=['POST'])
@login_required
def api_complete_task():
    data = request.json
    task_id = data.get('task_id')
    
    task = Task.query.filter_by(task_id=task_id, user_id=current_user.id).first()
    if not task:
        return jsonify({'success': False, 'error': 'Task not found'})
    
    if task.is_completed:
        return jsonify({'success': False, 'error': 'Task already completed'})
    
    # Mark as completed
    task.is_completed = True
    
    # Update XP if not negative habit
    if not task.is_negative_habit and task.xp_gained > 0:
        if task.attribute:
            task.attribute.current_xp += task.xp_gained
            
            # Check for level up milestone
            new_level = calculate_level_from_exp(task.attribute.current_xp)
            old_level = calculate_level_from_exp(task.attribute.current_xp - task.xp_gained)
            
            if new_level > old_level:
                milestone = Milestone(
                    user_id=current_user.id,
                    date=task.date,
                    title=f"Level Up: {task.attribute.name}",
                    description=f"Reached level {new_level} in {task.attribute.name}!",
                    attribute_id=task.attribute_id,
                    achievement_type='level_up'
                )
                db.session.add(milestone)
        
        if task.subskill:
            task.subskill.current_xp += task.xp_gained
    
    # Update stress
    if task.stress_effect != 0:
        stress_stat = CharacterStat.query.filter_by(
            user_id=current_user.id, 
            stat_name='Stress'
        ).first()
        if stress_stat:
            stress_stat.value = max(0, stress_stat.value + task.stress_effect)
    
    # Update daily stats
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
    
    # Ensure values are not None before incrementing
    if daily_stat.tasks_completed is None:
        daily_stat.tasks_completed = 0
    if daily_stat.total_xp_gained is None:
        daily_stat.total_xp_gained = 0
    
    daily_stat.tasks_completed += 1
    if not task.is_negative_habit:
        daily_stat.total_xp_gained += task.xp_gained
    
    db.session.commit()
    return jsonify({'success': True})

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
    task.negative_habit_done = did_negative  # Track the actual outcome
    
    if did_negative:
        # Did the negative habit - apply stress
        if task.stress_effect != 0:
            stress_stat = CharacterStat.query.filter_by(
                user_id=current_user.id, 
                stat_name='Stress'
            ).first()
            if stress_stat:
                stress_stat.value = max(0, stress_stat.value + abs(task.stress_effect))
    else:
        # Avoided the negative habit - give reward
        reward_xp = task.xp_gained or 25
        if task.attribute:
            task.attribute.current_xp += reward_xp
        if task.subskill:
            task.subskill.current_xp += reward_xp
        
        # Reduce stress for avoiding negative habit
        stress_stat = CharacterStat.query.filter_by(
            user_id=current_user.id, 
            stat_name='Stress'
        ).first()
        if stress_stat:
            stress_stat.value = max(0, stress_stat.value - 5)
    
    # Update daily stats
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
    
    # Ensure values are not None
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
    
    # If completed and gave XP, subtract it back
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
    
    # Get character stats
    character_stats = CharacterStat.query.filter_by(user_id=current_user.id).all()
    for stat in character_stats:
        stats[stat.stat_name] = stat.value
    
    # Get total completed tasks
    stats['Total Tasks Completed'] = Task.query.filter_by(
        user_id=current_user.id, 
        is_completed=True
    ).count()
    
    # UPDATED: More specific negative habit stats
    stats['Negative Habits Done'] = Task.query.filter_by(
        user_id=current_user.id, 
        is_completed=True, 
        is_negative_habit=True,
        negative_habit_done=True  # Only count when they actually did it
    ).count()
    
    stats['Negative Habits Avoided'] = Task.query.filter_by(
        user_id=current_user.id, 
        is_completed=True, 
        is_negative_habit=True,
        negative_habit_done=False  # Only count when they avoided it
    ).count()
    
    # Get skipped tasks for today
    today = datetime.date.today().isoformat()
    stats['Tasks Skipped Today'] = Task.query.filter_by(
        user_id=current_user.id, 
        date=today, 
        is_skipped=True
    ).count()
    
    # Get incomplete tasks for today
    stats['Tasks Remaining Today'] = Task.query.filter_by(
        user_id=current_user.id, 
        date=today, 
        is_completed=False, 
        is_skipped=False
    ).count()
    
    # Get total XP
    total_xp = db.session.query(db.func.sum(Attribute.current_xp)).filter_by(user_id=current_user.id).scalar()
    stats['Total XP'] = total_xp or 0
    
    # Get quest counts
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
    
    # Get total count
    total = Milestone.query.filter_by(user_id=current_user.id).count()
    
    # Get paginated milestones
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
    
    # Get completed tasks for context
    completed_tasks = Task.query.filter_by(
        user_id=current_user.id,
        date=date,
        is_completed=True,
        is_negative_habit=False
    ).all()
    
    # Generate narrative
    if completed_tasks:
        task_list = [f"{task.description} ({task.attribute.name if task.attribute else 'General'})" for task in completed_tasks]
        task_summary = ", ".join(task_list)
        prompt = f"Write a short, epic D&D-style narrative (150 words max) about an adventurer who accomplished: {task_summary}. Make it motivational and heroic."
    else:
        prompt = f"Write a short D&D-style narrative (150 words max) about a day of rest and preparation for an adventurer. Make it contemplative but hopeful."
    
    narrative_text = generate_ai_response(prompt, 
                                       "You are a D&D dungeon master creating daily adventure narratives.",
                                       api_key)
    
    # Save narrative
    existing_narrative = DailyNarrative.query.filter_by(
        user_id=current_user.id, 
        date=date
    ).first()
    
    if existing_narrative:
        existing_narrative.narrative = narrative_text
    else:
        new_narrative = DailyNarrative(
            user_id=current_user.id,
            date=date,
            narrative=narrative_text
        )
        db.session.add(new_narrative)
    
    db.session.commit()
    
    return jsonify({'narrative': narrative_text, 'date': date})

@app.route('/api/narratives')
@login_required
def api_get_narratives():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 3, type=int)
    
    # Get total count
    total = DailyNarrative.query.filter_by(user_id=current_user.id).count()
    
    # Get paginated narratives
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
    
    # Get daily stats for the month
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
    
    # Get date range
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    
    # Get user's attributes
    user_attributes = Attribute.query.filter_by(user_id=current_user.id).all()
    
    # Build date list
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.isoformat())
        current_date += datetime.timedelta(days=1)
    
    # Calculate XP progression for each attribute
    result = {
        'dates': dates,
        'attributes': {}
    }
    
    for attribute in user_attributes:
        levels = []
        running_xp = 0
        
        for date_str in dates:
            # Get XP gained on this date for this attribute
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

@app.route('/api/quests')
@login_required
def api_get_quests():
    quests = Quest.query.filter_by(user_id=current_user.id).order_by(
        (Quest.status == 'Active').desc(),
        Quest.due_date.asc(),
        Quest.start_date.desc()
    ).all()
    
    quests_data = []
    for quest in quests:
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
            'status': quest.status
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

@app.route('/api/complete_quest', methods=['POST'])
@login_required
def api_complete_quest():
    data = request.json
    quest_id = data.get('quest_id')
    
    quest = Quest.query.filter_by(quest_id=quest_id, user_id=current_user.id).first()
    if not quest or quest.status == 'Completed':
        return jsonify({'success': False, 'error': 'Quest not found or already completed'})
    
    # Mark as completed
    today = datetime.date.today().isoformat()
    quest.status = 'Completed'
    quest.completed_date = today
    
    # Add XP to attribute if specified
    if quest.attribute_focus:
        attribute = Attribute.query.filter_by(
            user_id=current_user.id,
            name=quest.attribute_focus
        ).first()
        if attribute:
            attribute.current_xp += quest.xp_reward
    
    # Add milestone
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
    
    # Parse response
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
    
    prompt = f"""Transform this modern self-improvement goal into an epic fantasy quest description (one sentence, max 20 words):
    
Original: "{description}"

Make it sound like a heroic medieval quest with fantasy elements. Keep the core meaning but make it epic and adventurous."""
    
    enhanced = generate_ai_response(prompt,
                                  "You are a fantasy quest master creating epic medieval quest descriptions.",
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
            'last_added_date': rt.last_added_date
        })
    
    return jsonify(tasks_data)

@app.route('/api/recurring_tasks', methods=['POST'])
@login_required
def api_add_recurring_task():
    data = request.json
    
    # Get attribute
    attribute = None
    if data.get('attribute'):
        attribute = Attribute.query.filter_by(
            user_id=current_user.id,
            name=data['attribute']
        ).first()
    
    # Calculate XP based on difficulty
    xp = 0 if data.get('is_negative_habit') else TASK_DIFFICULTIES.get(data.get('difficulty', 'medium'), 25)
    
    recurring_task = RecurringTask(
        user_id=current_user.id,
        description=data['description'],
        attribute_id=attribute.attribute_id if attribute else None,
        xp_value=xp,
        stress_effect=int(data.get('stress_effect', 0)),
        is_negative_habit=data.get('is_negative_habit', False),
        start_date=datetime.date.today().isoformat()
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
        # Get tasks to be deleted (for XP rollback)
        completed_tasks = Task.query.filter_by(
            user_id=current_user.id,
            date=date,
            is_completed=True,
            is_negative_habit=False
        ).all()
        
        # Rollback XP
        for task in completed_tasks:
            if task.attribute and task.xp_gained > 0:
                task.attribute.current_xp = max(0, task.attribute.current_xp - task.xp_gained)
            if task.subskill and task.xp_gained > 0:
                task.subskill.current_xp = max(0, task.subskill.current_xp - task.xp_gained)
        
        # Delete tasks
        Task.query.filter_by(user_id=current_user.id, date=date).delete()
        tasks_deleted = len(completed_tasks)
        
        # Reset daily stats
        DailyStat.query.filter_by(user_id=current_user.id, date=date).delete()
        
        # Delete narrative
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
        # Use the correct SQLAlchemy 2.x syntax
        with db.engine.connect() as connection:
            connection.execute(db.text('ALTER TABLE task ADD COLUMN negative_habit_done BOOLEAN DEFAULT NULL'))
            connection.commit()
        return "Successfully added negative_habit_done column to task table!"
    except Exception as e:
        # Check if column already exists (common error)
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            return "Column already exists - no action needed!"
        return f"Error adding column: {str(e)}"

# Initialize database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
