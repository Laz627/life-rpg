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
from sqlalchemy import func

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
    narrative_progress = db.relationship('NarrativeProgress', backref='user', uselist=False, cascade='all, delete-orphan')

    attributes = db.relationship('Attribute', backref='user', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='user', lazy=True, cascade='all, delete-orphan')
    quests = db.relationship('Quest', backref='user', lazy=True, cascade='all, delete-orphan')
    milestones = db.relationship('Milestone', backref='user', lazy=True, cascade='all, delete-orphan')
    narratives = db.relationship('DailyNarrative', backref='user', lazy=True, cascade='all, delete-orphan')
    recurring_tasks = db.relationship('RecurringTask', backref='user', lazy=True, cascade='all, delete-orphan')
    daily_stats = db.relationship('DailyStat', backref='user', lazy=True, cascade='all, delete-orphan')
    character_stats = db.relationship('CharacterStat', backref='user', lazy=True, cascade='all, delete-orphan')

class NarrativeProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    current_location = db.Column(db.String(100), default="The Crossroads Inn")
    main_quest = db.Column(db.Text, default="Seeking your destiny as an adventurer")
    companions = db.Column(db.Text, default="None yet")
    recent_events = db.Column(db.Text, default="You've just begun your adventure")
    story_day = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id'),)

class Attribute(db.Model):
    attribute_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    current_xp = db.Column(db.Integer, default=0)
    
    subskills = db.relationship('Subskill', backref='attribute', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='attribute', lazy=True)
    __table_args__ = (db.UniqueConstraint('user_id', 'name'),)

class Subskill(db.Model):
    subskill_id = db.Column(db.Integer, primary_key=True)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.attribute_id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    current_xp = db.Column(db.Integer, default=0)
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
    negative_habit_done = db.Column(db.Boolean, default=None)
    numeric_value = db.Column(db.Float, nullable=True)
    numeric_unit = db.Column(db.String(50), nullable=True)
    logged_numeric_value = db.Column(db.Float, nullable=True)

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
    steps = db.relationship('QuestStep', backref='quest', lazy=True, cascade='all, delete-orphan')

class QuestStep(db.Model):
    quest_step_id = db.Column(db.Integer, primary_key=True)
    quest_id = db.Column(db.Integer, db.ForeignKey('quest.quest_id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    is_completed = db.Column(db.Boolean, default=False)

class Milestone(db.Model):
    milestone_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.attribute_id'))
    achievement_type = db.Column(db.String(50), nullable=False)
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
    numeric_value = db.Column(db.Float, nullable=True)
    numeric_unit = db.Column(db.String(50), nullable=True)
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def calculate_exp_for_level(level):
    if level <= 1: return 0
    return int(100 * (level - 1) ** 2.2)

def calculate_level_from_exp(exp):
    if exp is None or exp <= 0: return 1
    return int(1 + (exp / 100) ** (1/2.2))

def generate_ai_response(prompt, system_message, api_key):
    try:
        openai.api_key = api_key
        response = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}], max_tokens=500)
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error with AI generation: {e}")
        return f"AI Error: {str(e)}"

def initialize_user_data(user):
    for attr_name, sub_list in ATTRIBUTES.items():
        attribute = Attribute(user_id=user.id, name=attr_name, description=f"Your {attr_name} attribute", current_xp=0)
        db.session.add(attribute)
        db.session.flush()
        for sub_name in sub_list:
            subskill = Subskill(attribute_id=attribute.attribute_id, name=sub_name, current_xp=0)
            db.session.add(subskill)
    db.session.add(NarrativeProgress(user_id=user.id))
    db.session.add(CharacterStat(user_id=user.id, stat_name='Stress', value=0))
    db.session.commit()

# --- Auth Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username, email, password = data.get('username'), data.get('email'), data.get('password')
        if not all([username, email, password]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400 if request.is_json else flash('All fields are required')
        if User.query.filter((User.username == username) | (User.email == email)).first():
            return jsonify({'success': False, 'error': 'Username or email already exists'}), 400 if request.is_json else flash('Username or email already exists')
        user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        initialize_user_data(user)
        login_user(user)
        return jsonify({'success': True, 'redirect': '/'}) if request.is_json else redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username, password = data.get('username'), data.get('password')
        user = User.query.filter((User.username == username) | (User.email == username)).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return jsonify({'success': True, 'redirect': '/'}) if request.is_json else redirect(url_for('index'))
        if request.is_json:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        flash('Invalid username/email or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- Main & API Routes ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

@app.route('/api/test_api_key', methods=['POST'])
@login_required
def test_api_key():
    api_key = request.json.get('api_key')
    if not api_key: return jsonify({'success': False, 'error': 'No API key provided'})
    try:
        openai.api_key = api_key
        openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "test"}], max_tokens=5)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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
        subskills_data = []
        for sub in attr.subskills:
            sub_level = calculate_level_from_exp(sub.current_xp)
            sub_current_xp = calculate_exp_for_level(sub_level)
            sub_next_xp = calculate_exp_for_level(sub_level + 1)
            subskills_data.append({'id': sub.subskill_id, 'name': sub.name, 'level': sub_level, 'total_xp': sub.current_xp, 'xp_progress': sub.current_xp - sub_current_xp, 'xp_needed': sub_next_xp - sub_current_xp, 'progress_percent': ((sub.current_xp - sub_current_xp) / (sub_next_xp - sub_current_xp) * 100) if (sub_next_xp - sub_current_xp) > 0 else 100})
        attributes_data.append({'id': attr.attribute_id, 'name': attr.name, 'level': level, 'total_xp': attr.current_xp, 'xp_progress': xp_progress, 'xp_needed': xp_needed, 'progress_percent': (xp_progress / xp_needed * 100) if xp_needed > 0 else 100, 'subskills': subskills_data})
    return jsonify(attributes_data)

@app.route('/api/tasks')
@login_required
def api_get_tasks():
    date = request.args.get('date', datetime.date.today().isoformat())
    recurring_tasks = RecurringTask.query.filter(RecurringTask.user_id == current_user.id, RecurringTask.is_active == True, RecurringTask.start_date <= date).all()
    for rt in recurring_tasks:
        if not Task.query.filter_by(user_id=current_user.id, date=date, description=rt.description).first():
            db.session.add(Task(user_id=current_user.id, date=date, description=rt.description, task_type='recurring', attribute_id=rt.attribute_id, subskill_id=rt.subskill_id, xp_gained=rt.xp_value, stress_effect=rt.stress_effect, is_negative_habit=rt.is_negative_habit, numeric_value=rt.numeric_value, numeric_unit=rt.numeric_unit))
    db.session.commit()
    tasks = Task.query.filter_by(user_id=current_user.id, date=date).order_by(Task.is_completed, Task.is_skipped, Task.task_id.desc()).all()
    tasks_data = [{'id': task.task_id, 'description': task.description, 'type': task.task_type, 'completed': task.is_completed, 'skipped': task.is_skipped, 'attribute': task.attribute.name if task.attribute else None, 'subskill': task.subskill.name if task.subskill else None, 'xp': task.xp_gained, 'stress_effect': task.stress_effect, 'is_negative_habit': task.is_negative_habit, 'numeric_value': task.numeric_value, 'numeric_unit': task.numeric_unit, 'logged_numeric_value': task.logged_numeric_value} for task in tasks]
    return jsonify(tasks_data)

@app.route('/api/add_task', methods=['POST'])
@login_required
def api_add_task():
    data = request.json
    is_negative = data.get('is_negative_habit', False)
    numeric_unit = data.get('numeric_unit') or ('occurrence' if is_negative else None)
    task = Task(user_id=current_user.id, date=data.get('date', datetime.date.today().isoformat()), description=data['description'], task_type=data.get('type', 'general'), xp_gained=0 if is_negative else TASK_DIFFICULTIES.get(data.get('difficulty', 'medium'), 25), stress_effect=int(data.get('stress_effect', 0)), is_negative_habit=is_negative, numeric_value=data.get('numeric_value'), numeric_unit=numeric_unit)
    if data.get('attribute'):
        attribute = Attribute.query.filter_by(user_id=current_user.id, name=data['attribute']).first()
        if attribute: task.attribute_id = attribute.attribute_id
        if data.get('subskill'):
            subskill = Subskill.query.filter_by(attribute_id=attribute.attribute_id, name=data['subskill']).first()
            if subskill: task.subskill_id = subskill.subskill_id
    db.session.add(task)
    db.session.commit()
    return jsonify({'success': True, 'task_id': task.task_id})

@app.route('/api/complete_task', methods=['POST'])
@login_required
def api_complete_task():
    data = request.json
    task = Task.query.get_or_404(data.get('task_id'))
    if task.user_id != current_user.id or task.is_completed: return jsonify({'success': False, 'error': 'Task not found or already completed'}), 404
    task.is_completed = True
    if 'logged_numeric_value' in data:
        try: task.logged_numeric_value = float(data['logged_numeric_value'])
        except (ValueError, TypeError): pass
    is_success = (not task.is_negative_habit and (task.numeric_unit is None or (task.logged_numeric_value is not None and task.logged_numeric_value > 0))) or \
                 (task.is_negative_habit and task.logged_numeric_value is not None and task.logged_numeric_value <= (task.numeric_value or 0))
    if is_success:
        reward_xp = task.xp_gained or 25
        if task.attribute: task.attribute.current_xp += reward_xp
        if task.subskill: task.subskill.current_xp += reward_xp
        if task.is_negative_habit:
            stress_stat = CharacterStat.query.filter_by(user_id=current_user.id, stat_name='Stress').first()
            if stress_stat: stress_stat.value = max(0, stress_stat.value - 5)
    elif task.is_negative_habit:
        stress_stat = CharacterStat.query.filter_by(user_id=current_user.id, stat_name='Stress').first()
        if stress_stat and task.stress_effect != 0: stress_stat.value = max(0, stress_stat.value + abs(task.stress_effect))
    today_iso = datetime.date.today().isoformat()
    daily_stat = DailyStat.query.filter_by(user_id=current_user.id, date=today_iso).first()
    if not daily_stat:
        daily_stat = DailyStat(user_id=current_user.id, date=today_iso, tasks_completed=0, total_xp_gained=0)
        db.session.add(daily_stat)
    if is_success:
        daily_stat.tasks_completed = (daily_stat.tasks_completed or 0) + 1
        daily_stat.total_xp_gained = (daily_stat.total_xp_gained or 0) + (task.xp_gained or 25)
    db.session.commit()
    return jsonify({'success': True, 'was_success': is_success})

@app.route('/api/skip_task', methods=['POST'])
@login_required
def api_skip_task():
    task = Task.query.get_or_404(request.json.get('task_id'))
    if task.user_id != current_user.id or task.is_completed or task.is_skipped: return jsonify({'success': False, 'error': 'Task not found or already processed'}), 404
    task.is_skipped = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/delete_task', methods=['POST'])
@login_required
def api_delete_task():
    task = Task.query.get_or_404(request.json.get('task_id'))
    if task.user_id != current_user.id: return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    if task.is_completed and not task.is_negative_habit and task.xp_gained > 0:
        if task.attribute: task.attribute.current_xp = max(0, task.attribute.current_xp - task.xp_gained)
        if task.subskill: task.subskill.current_xp = max(0, task.subskill.current_xp - task.xp_gained)
    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/stats')
@login_required
def api_get_stats():
    stats = {s.stat_name: s.value for s in CharacterStat.query.filter_by(user_id=current_user.id).all()}
    stats['Total Tasks Completed'] = Task.query.filter_by(user_id=current_user.id, is_completed=True).count()
    stats['Negative Habits Done'] = Task.query.filter_by(user_id=current_user.id, is_completed=True, is_negative_habit=True, negative_habit_done=True).count()
    stats['Negative Habits Avoided'] = Task.query.filter_by(user_id=current_user.id, is_completed=True, is_negative_habit=True, negative_habit_done=False).count()
    today_iso = datetime.date.today().isoformat()
    stats['Tasks Skipped Today'] = Task.query.filter_by(user_id=current_user.id, date=today_iso, is_skipped=True).count()
    stats['Tasks Remaining Today'] = Task.query.filter_by(user_id=current_user.id, date=today_iso, is_completed=False, is_skipped=False).count()
    stats['Total XP'] = db.session.query(db.func.sum(Attribute.current_xp)).filter_by(user_id=current_user.id).scalar() or 0
    stats['Active Quests'] = Quest.query.filter_by(user_id=current_user.id, status='Active').count()
    stats['Completed Quests'] = Quest.query.filter_by(user_id=current_user.id, status='Completed').count()
    return jsonify(stats)

@app.route('/api/milestones')
@login_required
def api_get_milestones():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    milestones = Milestone.query.filter_by(user_id=current_user.id).order_by(Milestone.date.desc(), Milestone.milestone_id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    milestones_data = [{'id': m.milestone_id, 'date': m.date, 'title': m.title, 'description': m.description, 'type': m.achievement_type, 'attribute': m.attribute.name if m.attribute else None} for m in milestones.items]
    return jsonify({'milestones': milestones_data, 'current_page': page, 'pages': milestones.pages, 'total': milestones.total})

@app.route('/api/delete_milestone', methods=['POST'])
@login_required
def api_delete_milestone():
    milestone = Milestone.query.get_or_404(request.json.get('milestone_id'))
    if milestone.user_id != current_user.id: return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    db.session.delete(milestone)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/narrative')
@login_required
def api_get_narrative():
    date = request.args.get('date', datetime.date.today().isoformat())
    narrative = DailyNarrative.query.filter_by(user_id=current_user.id, date=date).first()
    return jsonify({'date': date, 'narrative': narrative.narrative if narrative else "No adventure recorded for this day yet..."})

@app.route('/api/generate_narrative', methods=['POST'])
@login_required
def api_generate_narrative():
    # ... This function remains the same as your last version ...
    # (It's long, so keeping it collapsed for brevity, but it's unchanged)
    data=request.json;api_key=data.get('api_key');date=data.get('date',datetime.date.today().isoformat());
    if not api_key:return jsonify({'error':'API key required'}),400
    progress=NarrativeProgress.query.filter_by(user_id=current_user.id).first();
    if not progress:progress=NarrativeProgress(user_id=current_user.id);db.session.add(progress);db.session.flush()
    last_narrative=DailyNarrative.query.filter_by(user_id=current_user.id).order_by(DailyNarrative.date.desc()).first()
    context=f"Current Story State:\n- Location: {progress.current_location}\n- Main Quest: {progress.main_quest}\n- Companions: {progress.companions}\n- Recent Events: {progress.recent_events}\n- Story Day: {progress.story_day}"
    if last_narrative:context+=f"\nYesterday's Events: {last_narrative.narrative}"
    story_info=get_story_phase_and_focus(progress.story_day)
    prompt=f"Write today's D&D adventure entry for an ongoing epic story. \n\nSTORY PROGRESSION:\n- Overall Day: {progress.story_day}\n- Chapter: {story_info['chapter']} \n- Day in Chapter: {story_info['day_in_chapter']}\n- Phase: {story_info['phase']}\n- Power Level: {story_info['complexity']}\n\n{context}\n\nWRITING GUIDELINES:\n- {story_info['focus']}\n- {story_info['scope']}\n- Advance the story meaningfully - no repetition or circular events\n- Include specific details: names, places, discoveries, or encounters\n- Show character growth and escalating power/responsibility\n- Keep it engaging and around 120-150 words\n- End with a hook for tomorrow\n\nSPECIAL INSTRUCTIONS:\n{get_special_chapter_instructions(story_info['day_in_chapter'], story_info['chapter'])}\n\nAt the end, update the story state in this format:\n[LOCATION: new location if changed]\n[QUEST: updated main quest if evolved]\n[COMPANIONS: current companions]\n[EVENTS: summary of today's key events]"
    system_message="You are a master D&D dungeon master creating a continuous, evolving epic saga. Each day should meaningfully advance the narrative with proper story structure. Create memorable moments that build toward greater adventures. Avoid repetition and ensure real progression through escalating challenges and character growth."
    narrative_text=generate_ai_response(prompt,system_message,api_key)
    story_updates={};clean_narrative=[]
    for line in narrative_text.split('\n'):
        if line.startswith('[LOCATION:'):story_updates['location']=line.replace('[LOCATION:','').replace(']','').strip()
        elif line.startswith('[QUEST:'):story_updates['quest']=line.replace('[QUEST:','').replace(']','').strip()
        elif line.startswith('[COMPANIONS:'):story_updates['companions']=line.replace('[COMPANIONS:','').replace(']','').strip()
        elif line.startswith('[EVENTS:'):story_updates['events']=line.replace('[EVENTS:','').replace(']','').strip()
        else:clean_narrative.append(line)
    final_narrative='\n'.join(clean_narrative).strip()
    if story_updates.get('location'):progress.current_location=story_updates['location']
    if story_updates.get('quest'):progress.main_quest=story_updates['quest']
    if story_updates.get('companions'):progress.companions=story_updates['companions']
    if story_updates.get('events'):progress.recent_events=story_updates['events']
    progress.story_day+=1;progress.updated_at=datetime.datetime.utcnow()
    existing_narrative=DailyNarrative.query.filter_by(user_id=current_user.id,date=date).first()
    if existing_narrative:existing_narrative.narrative=final_narrative
    else:new_narrative=DailyNarrative(user_id=current_user.id,date=date,narrative=final_narrative);db.session.add(new_narrative)
    db.session.commit()
    return jsonify({'narrative':final_narrative,'date':date,'story_day':progress.story_day-1,'location':progress.current_location,'quest':progress.main_quest,'chapter':story_info['chapter'],'phase':story_info['phase'],'complexity':story_info['complexity']})

def get_story_phase_and_focus(story_day):
    chapter = (story_day - 1) // 50 + 1
    day_in_chapter = ((story_day - 1) % 50) + 1
    if day_in_chapter <= 10: phase, focus = "Opening", f"Chapter {chapter} begins! New lands, new challenges." if chapter > 1 else "Begin your legendary journey."
    elif day_in_chapter <= 25: phase, focus = "Rising Action", "Develop the main plot, introduce allies, enemies, and mysteries."
    elif day_in_chapter <= 40: phase, focus = "Climax Building", "Major conflicts intensify, prepare for the climax."
    elif day_in_chapter <= 45: phase, focus = "Climax", "The chapter's main conflict reaches its peak!"
    else: phase, focus = "Resolution", "Conclude the arc, celebrate victories, and set up the next adventure."
    if story_day <= 50: complexity, scope = "Local Hero", "Focus on personal growth and local threats."
    elif story_day <= 100: complexity, scope = "Regional Champion", "Expand to affect kingdoms, face greater magical threats."
    elif story_day <= 200: complexity, scope = "Continental Legend", "Multi-kingdom politics, ancient evils."
    else: complexity, scope = "Mythic Figure", "Godlike powers, planar threats."
    return {'chapter': chapter, 'day_in_chapter': day_in_chapter, 'phase': phase, 'focus': focus, 'complexity': complexity, 'scope': scope}

def get_special_chapter_instructions(day_in_chapter, chapter_num):
    if day_in_chapter == 1 and chapter_num > 1: return f"CHAPTER {chapter_num} OPENING: Introduce new setting, escalated threats."
    if day_in_chapter == 50: return "CHAPTER FINALE: Provide satisfying conclusion to this chapter's main arc."
    if 45 <= day_in_chapter <= 49: return "CLIMAX SEQUENCE: This is peak drama! Make it epic."
    return "Continue the natural story progression."

@app.route('/api/narratives')
@login_required
def api_get_narratives():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 3, type=int)
    narratives = DailyNarrative.query.filter_by(user_id=current_user.id).order_by(DailyNarrative.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({'narratives': [{'date': n.date, 'narrative': n.narrative} for n in narratives.items], 'current_page': page, 'pages': narratives.pages, 'total': narratives.total})

@app.route('/api/heatmap')
@login_required
def api_get_heatmap():
    year = request.args.get('year', datetime.date.today().year, type=int)
    month = request.args.get('month', datetime.date.today().month, type=int)
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year if month < 12 else year + 1}-{(month % 12) + 1:02d}-01"
    stats = DailyStat.query.filter(DailyStat.user_id == current_user.id, DailyStat.date >= start_date, DailyStat.date < end_date).all()
    return jsonify([{'date': s.date, 'count': s.tasks_completed, 'xp': s.total_xp_gained} for s in stats])

@app.route('/api/attribute_history')
@login_required
def api_get_attribute_history():
    days = request.args.get('days', 30, type=int)
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    attributes = Attribute.query.filter_by(user_id=current_user.id).all()
    dates = [(start_date + datetime.timedelta(days=i)).isoformat() for i in range(days + 1)]
    result = {'dates': dates, 'attributes': {}}
    for attr in attributes:
        daily_xps = {row[0]: row[1] for row in db.session.query(Task.date, db.func.sum(Task.xp_gained)).filter(Task.user_id==current_user.id, Task.attribute_id==attr.attribute_id, Task.date.in_(dates), Task.is_completed==True, Task.is_negative_habit==False).group_by(Task.date).all()}
        running_xp = 0
        result['attributes'][attr.name] = [calculate_level_from_exp(running_xp := running_xp + daily_xps.get(d, 0)) for d in dates]
    return jsonify(result)

@app.route('/api/get_numeric_habits')
@login_required
def get_numeric_habits():
    habits = db.session.query(Task.description).filter(Task.user_id == current_user.id, Task.numeric_unit.isnot(None)).distinct().all()
    return jsonify([h[0] for h in habits])

@app.route('/api/habit_progress')
@login_required
def get_habit_progress():
    desc = request.args.get('description')
    if not desc: return jsonify({'error': 'Habit description is required'}), 400
    habit_info = RecurringTask.query.filter_by(user_id=current_user.id, description=desc).first() or Task.query.filter_by(user_id=current_user.id, description=desc).first()
    is_neg = habit_info.is_negative_habit if habit_info else False
    unit = habit_info.numeric_unit if habit_info else ''
    today = date.today()
    def get_stats(start, end):
        stats = db.session.query(func.sum(Task.logged_numeric_value), func.avg(Task.logged_numeric_value)).filter(Task.user_id==current_user.id, Task.description==desc, Task.is_completed==True, Task.logged_numeric_value.isnot(None), Task.date>=start.isoformat(), Task.date<=end.isoformat()).first()
        return {'total': stats[0] or 0, 'avg': stats[1] or 0}
    this_week_start = today - timedelta(days=today.weekday())
    this_week_stats = get_stats(this_week_start, this_week_start + timedelta(days=6))
    last_week_stats = get_stats(this_week_start - timedelta(days=7), this_week_start - timedelta(days=1))
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    this_month_stats = get_stats(this_month_start, (this_month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1))
    last_month_stats = get_stats(last_month_start, last_month_end)
    def calc_change(curr, prev, is_n):
        if prev > 0: change = ((curr - prev) / prev) * 100; return round(-change if is_n else change, 1)
        return 100 if curr > 0 and not is_n else (-100 if curr > 0 and is_n else 0)
    return jsonify({
        'week': {'this_week': this_week_stats, 'last_week': last_week_stats, 'total_change': calc_change(this_week_stats['total'], last_week_stats['total'], is_neg), 'avg_change': calc_change(this_week_stats['avg'], last_week_stats['avg'], is_neg)},
        'month': {'this_month': this_month_stats, 'last_month': last_month_stats, 'total_change': calc_change(this_month_stats['total'], last_month_stats['total'], is_neg), 'avg_change': calc_change(this_month_stats['avg'], last_month_stats['avg'], is_neg)},
        'unit': unit, 'is_negative': is_neg
    })

# --- Quest Management ---
@app.route('/api/quests', methods=['GET'])
@login_required
def api_get_quests():
    quests = Quest.query.filter_by(user_id=current_user.id).order_by((Quest.status == 'Active').desc(), Quest.due_date.asc(), Quest.start_date.desc()).all()
    quests_data = []
    for q in quests:
        total_steps = len(q.steps)
        completed_steps = sum(1 for step in q.steps if step.is_completed)
        quests_data.append({
            'id': q.quest_id, 'title': q.title, 'description': q.description, 'difficulty': q.difficulty,
            'xp_reward': q.xp_reward, 'attribute_focus': q.attribute_focus, 'start_date': q.start_date,
            'due_date': q.due_date, 'completed_date': q.completed_date, 'status': q.status,
            'progress': (completed_steps / total_steps * 100) if total_steps > 0 else 0,
            'steps': [{'id': s.quest_step_id, 'description': s.description, 'completed': s.is_completed} for s in q.steps]
        })
    return jsonify(quests_data)

@app.route('/api/quests', methods=['POST'])
@login_required
def api_add_quest():
    data = request.json
    quest = Quest(user_id=current_user.id, title=data['title'], description=data.get('description', ''), difficulty=data.get('difficulty', 'Medium'), xp_reward=data.get('xp_reward', 100), attribute_focus=data.get('attribute_focus', ''), start_date=datetime.date.today().isoformat(), due_date=data.get('due_date'))
    db.session.add(quest)
    db.session.commit()
    return jsonify({'success': True, 'quest_id': quest.quest_id})

@app.route('/api/quests/<int:quest_id>', methods=['PUT'])
@login_required
def api_update_quest(quest_id):
    quest = Quest.query.get_or_404(quest_id)
    if quest.user_id != current_user.id: return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    data = request.json
    quest.title = data.get('title', quest.title)
    quest.description = data.get('description', quest.description)
    quest.difficulty = data.get('difficulty', quest.difficulty)
    quest.attribute_focus = data.get('attribute_focus', quest.attribute_focus)
    quest.due_date = data.get('due_date', quest.due_date)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/quests/<int:quest_id>/add_step', methods=['POST'])
@login_required
def api_add_quest_step(quest_id):
    quest = Quest.query.get_or_404(quest_id)
    if quest.user_id != current_user.id: return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    data = request.json
    if not data.get('description'): return jsonify({'success': False, 'error': 'Step description cannot be empty'}), 400
    step = QuestStep(quest_id=quest_id, description=data['description'])
    db.session.add(step)
    db.session.commit()
    return jsonify({'success': True, 'step_id': step.quest_step_id})

@app.route('/api/quest_steps/<int:step_id>/toggle', methods=['POST'])
@login_required
def api_toggle_quest_step(step_id):
    step = QuestStep.query.get_or_404(step_id)
    if step.quest.user_id != current_user.id: return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    step.is_completed = not step.is_completed
    db.session.commit()
    return jsonify({'success': True, 'is_completed': step.is_completed})

@app.route('/api/quest_steps/<int:step_id>', methods=['DELETE'])
@login_required
def api_delete_quest_step(step_id):
    step = QuestStep.query.get_or_404(step_id)
    if step.quest.user_id != current_user.id: return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    db.session.delete(step)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/complete_quest', methods=['POST'])
@login_required
def api_complete_quest():
    quest = Quest.query.get_or_404(request.json.get('quest_id'))
    if quest.user_id != current_user.id or quest.status == 'Completed': return jsonify({'success': False, 'error': 'Quest not found or already completed'}), 404
    today = datetime.date.today().isoformat()
    quest.status = 'Completed'
    quest.completed_date = today
    if quest.attribute_focus:
        attribute = Attribute.query.filter_by(user_id=current_user.id, name=quest.attribute_focus).first()
        if attribute: attribute.current_xp += quest.xp_reward
    db.session.add(Milestone(user_id=current_user.id, date=today, title=f"Quest Completed: {quest.title}", description=f"Successfully completed the quest '{quest.title}' and earned {quest.xp_reward} XP!", achievement_type='quest'))
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/generate_quest', methods=['POST'])
@login_required
def api_generate_quest():
    data = request.json
    if not data.get('api_key'): return jsonify({'error': 'API key required'}), 400
    attribute = data.get('attribute_focus') or random.choice(list(ATTRIBUTES.keys()))
    difficulty = data.get('difficulty') or random.choice(QUEST_DIFFICULTIES)
    prompt = f"Create a self-improvement quest for {attribute} at {difficulty} difficulty. Format:\nTitle: [quest title]\nDescription: [50 word description]"
    response = generate_ai_response(prompt, "You are a quest master.", data['api_key'])
    title = next((l.replace('Title:', '').strip() for l in response.split('\n') if l.startswith('Title:')), "New Quest")
    description = next((l.replace('Description:', '').strip() for l in response.split('\n') if l.startswith('Description:')), response)
    xp = {"Easy": 50, "Medium": 100, "Hard": 175, "Epic": 250}
    due = (datetime.date.today() + datetime.timedelta(days={"Easy": 3, "Medium": 7, "Hard": 14, "Epic": 21}.get(difficulty, 7))).isoformat()
    return jsonify({'title': title, 'description': description, 'difficulty': difficulty, 'attribute_focus': attribute, 'xp_reward': xp.get(difficulty, 100), 'due_date': due})

@app.route('/api/enhance_quest_description', methods=['POST'])
@login_required
def api_enhance_quest_description():
    data = request.json
    if not data.get('api_key'): return jsonify({'error': 'API key required'}), 400
    if not data.get('description'): return jsonify({'error': 'Description required'}), 400
    prompt = f"Transform this goal into an epic fantasy quest description (15-25 words):\n\nGoal: \"{data['description']}\""
    return jsonify({'enhanced_description': generate_ai_response(prompt, "You are a master storyteller.", data['api_key'])})

@app.route('/api/recurring_tasks', methods=['GET'])
@login_required
def api_get_recurring_tasks():
    recurring_tasks = RecurringTask.query.filter_by(user_id=current_user.id).order_by(RecurringTask.is_active.desc(), RecurringTask.description).all()
    return jsonify([{'recurring_task_id': rt.recurring_task_id, 'description': rt.description, 'attribute_name': rt.attribute.name if rt.attribute else None, 'subskill_name': rt.subskill.name if rt.subskill else None, 'xp_value': rt.xp_value, 'stress_effect': rt.stress_effect, 'is_negative_habit': rt.is_negative_habit, 'is_active': rt.is_active, 'last_added_date': rt.last_added_date, 'numeric_value': rt.numeric_value, 'numeric_unit': rt.numeric_unit} for rt in recurring_tasks])

@app.route('/api/recurring_tasks', methods=['POST'])
@login_required
def api_add_recurring_task():
    data = request.json
    is_negative = data.get('is_negative_habit', False)
    numeric_unit = data.get('numeric_unit') or ('occurrence' if is_negative else None)
    rt = RecurringTask(user_id=current_user.id, description=data['description'], xp_value=0 if is_negative else TASK_DIFFICULTIES.get(data.get('difficulty', 'medium'), 25), stress_effect=int(data.get('stress_effect', 0)), is_negative_habit=is_negative, start_date=datetime.date.today().isoformat(), numeric_value=data.get('numeric_value'), numeric_unit=numeric_unit)
    if data.get('attribute'):
        attribute = Attribute.query.filter_by(user_id=current_user.id, name=data['attribute']).first()
        if attribute: rt.attribute_id = attribute.attribute_id
    db.session.add(rt)
    db.session.commit()
    return jsonify({'success': True, 'recurring_task_id': rt.recurring_task_id})

@app.route('/api/recurring_tasks/<int:rt_id>', methods=['DELETE'])
@login_required
def api_delete_recurring_task(rt_id):
    rt = RecurringTask.query.get_or_404(rt_id)
    if rt.user_id != current_user.id: return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    db.session.delete(rt)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/recurring_tasks/<int:rt_id>/toggle_active', methods=['POST'])
@login_required
def api_toggle_recurring_task(rt_id):
    rt = RecurringTask.query.get_or_404(rt_id)
    if rt.user_id != current_user.id: return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    rt.is_active = not rt.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': rt.is_active})

@app.route('/api/reset_day', methods=['POST'])
@login_required
def api_reset_day():
    date = request.json.get('date', datetime.date.today().isoformat())
    try:
        completed = Task.query.filter_by(user_id=current_user.id, date=date, is_completed=True, is_negative_habit=False).all()
        for t in completed:
            if t.attribute and t.xp_gained > 0: t.attribute.current_xp = max(0, t.attribute.current_xp - t.xp_gained)
            if t.subskill and t.xp_gained > 0: t.subskill.current_xp = max(0, t.subskill.current_xp - t.xp_gained)
        Task.query.filter_by(user_id=current_user.id, date=date).delete()
        DailyStat.query.filter_by(user_id=current_user.id, date=date).delete()
        DailyNarrative.query.filter_by(user_id=current_user.id, date=date).delete()
        db.session.commit()
        return jsonify({'success': True, 'date': date, 'tasks_deleted': len(completed)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/story_progress')
@login_required
def api_get_story_progress():
    progress = NarrativeProgress.query.filter_by(user_id=current_user.id).first()
    if not progress: return jsonify({'story_day': 1, 'location': 'The Crossroads Inn', 'main_quest': 'Seeking your destiny', 'companions': 'None yet'})
    return jsonify({'story_day': progress.story_day, 'location': progress.current_location, 'main_quest': progress.main_quest, 'companions': progress.companions, 'recent_events': progress.recent_events})

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
