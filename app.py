import os
import sqlite3
import openai
import datetime
import random
import time
import math
import json
import calendar
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import contextlib
import re

# --- Configuration ---
app = Flask(__name__)
CORS(app)

# Database will be created in user's app data
DB_FILE = "life_rpg.db"

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

# --- Database Functions ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Create all tables with complete schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attributes (
            attribute_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            current_xp INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subskills (
            subskill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            attribute_id INTEGER,
            name TEXT NOT NULL,
            current_xp INTEGER DEFAULT 0,
            FOREIGN KEY (attribute_id) REFERENCES attributes(attribute_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            task_type TEXT NOT NULL,
            attribute_id INTEGER,
            subskill_id INTEGER,
            xp_gained INTEGER DEFAULT 0,
            stress_effect INTEGER DEFAULT 0,
            is_completed BOOLEAN DEFAULT 0,
            quantity REAL DEFAULT 1,
            is_negative_habit BOOLEAN DEFAULT 0,
            FOREIGN KEY (attribute_id) REFERENCES attributes(attribute_id),
            FOREIGN KEY (subskill_id) REFERENCES subskills(subskill_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            stress_level INTEGER DEFAULT 0,
            tasks_completed INTEGER DEFAULT 0,
            total_xp_gained INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_stats (
            stat_name TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS milestones (
            milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            attribute_id INTEGER,
            achievement_type TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_narratives (
            date TEXT PRIMARY KEY,
            narrative TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            difficulty TEXT,
            xp_reward INTEGER,
            attribute_focus TEXT,
            start_date TEXT NOT NULL,
            due_date TEXT,
            completed_date TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurring_tasks (
            recurring_task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            attribute_id INTEGER,
            subskill_id INTEGER,
            xp_value INTEGER DEFAULT 0,
            stress_effect INTEGER DEFAULT 0,
            is_negative_habit BOOLEAN DEFAULT 0,
            start_date TEXT NOT NULL,
            last_added_date TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    """)
    
    # Initialize attributes and subskills
    for attr_name, sub_list in ATTRIBUTES.items():
        cursor.execute("INSERT OR IGNORE INTO attributes (name, description) VALUES (?, ?)",
                      (attr_name, f"Your {attr_name} attribute"))
        
        cursor.execute("SELECT attribute_id FROM attributes WHERE name = ?", (attr_name,))
        result = cursor.fetchone()
        if result:
            attr_id = result[0]
            for sub_name in sub_list:
                cursor.execute("INSERT OR IGNORE INTO subskills (attribute_id, name) VALUES (?, ?)",
                              (attr_id, sub_name))
    
    cursor.execute("INSERT OR IGNORE INTO character_stats (stat_name, value) VALUES ('Stress', 0)")
    
    conn.commit()
    conn.close()

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
            model="gpt-3.5-turbo",
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

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/init')
def api_init():
    init_db()
    return jsonify({'success': True})

@app.route('/api/test_api_key', methods=['POST'])
def test_api_key():
    """Test if the provided API key is valid"""
    data = request.json
    api_key = data.get('api_key')
    
    if not api_key:
        return jsonify({'success': False, 'error': 'No API key provided'})
    
    try:
        openai.api_key = api_key
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        return jsonify({'success': True})
    except Exception as e:
        error_message = str(e)
        print(f"API key test failed: {error_message}")
        return jsonify({'success': False, 'error': error_message})

@app.route('/api/attributes')
def api_get_attributes():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT attribute_id, name, current_xp FROM attributes ORDER BY name")
    attributes = []
    
    for row in cursor.fetchall():
        attr_id, name, xp = row
        level = calculate_level_from_exp(xp)
        
        # Calculate progress
        current_level_xp = calculate_exp_for_level(level)
        next_level_xp = calculate_exp_for_level(level + 1)
        xp_progress = xp - current_level_xp
        xp_needed = next_level_xp - current_level_xp
        progress_percent = (xp_progress / xp_needed * 100) if xp_needed > 0 else 100
        
        # Get subskills
        cursor.execute("SELECT subskill_id, name, current_xp FROM subskills WHERE attribute_id = ?", (attr_id,))
        subskills = []
        for sub_row in cursor.fetchall():
            sub_id, sub_name, sub_xp = sub_row
            sub_level = calculate_level_from_exp(sub_xp)
            sub_current_level_xp = calculate_exp_for_level(sub_level)
            sub_next_level_xp = calculate_exp_for_level(sub_level + 1)
            sub_xp_progress = sub_xp - sub_current_level_xp
            sub_xp_needed = sub_next_level_xp - sub_current_level_xp
            sub_progress_percent = (sub_xp_progress / sub_xp_needed * 100) if sub_xp_needed > 0 else 100
            
            subskills.append({
                'id': sub_id,
                'name': sub_name,
                'level': sub_level,
                'total_xp': sub_xp,
                'xp_progress': sub_xp_progress,
                'xp_needed': sub_xp_needed,
                'progress_percent': sub_progress_percent
            })
        
        attributes.append({
            'id': attr_id,
            'name': name,
            'level': level,
            'total_xp': xp,
            'xp_progress': xp_progress,
            'xp_needed': xp_needed,
            'progress_percent': progress_percent,
            'subskills': subskills
        })
    
    conn.close()
    return jsonify(attributes)

@app.route('/api/tasks')
def api_get_tasks():
    date = request.args.get('date', datetime.date.today().isoformat())
    conn = get_db()
    cursor = conn.cursor()
    
    # Process recurring tasks for this date
    cursor.execute("""
        SELECT recurring_task_id, description, attribute_id, subskill_id, 
               xp_value, stress_effect, is_negative_habit
        FROM recurring_tasks 
        WHERE is_active = 1 AND start_date <= ?
    """, (date,))
    
    for row in cursor.fetchall():
        rt_id, desc, attr_id, sub_id, xp, stress, is_neg = row
        
        # Check if already added for this date
        cursor.execute("SELECT task_id FROM tasks WHERE date = ? AND description = ?", (date, desc))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO tasks (date, description, task_type, attribute_id, subskill_id,
                                 xp_gained, stress_effect, is_negative_habit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (date, desc, 'recurring', attr_id, sub_id, xp, stress, is_neg))
    
    conn.commit()
    
    # Get tasks for the date
    cursor.execute("""
        SELECT t.task_id, t.description, t.task_type, t.is_completed, 
               a.name as attribute_name, s.name as subskill_name,
               t.xp_gained, t.stress_effect, t.is_negative_habit
        FROM tasks t
        LEFT JOIN attributes a ON t.attribute_id = a.attribute_id
        LEFT JOIN subskills s ON t.subskill_id = s.subskill_id
        WHERE t.date = ?
        ORDER BY t.is_completed, t.task_id DESC
    """, (date,))
    
    tasks = []
    for row in cursor.fetchall():
        tasks.append({
            'id': row[0],
            'description': row[1],
            'type': row[2],
            'completed': bool(row[3]),
            'attribute': row[4],
            'subskill': row[5],
            'xp': row[6],
            'stress_effect': row[7],
            'is_negative_habit': bool(row[8])
        })
    
    conn.close()
    return jsonify(tasks)

@app.route('/api/add_task', methods=['POST'])
def api_add_task():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    # Get attribute and subskill IDs
    attr_id = None
    sub_id = None
    
    if data.get('attribute'):
        cursor.execute("SELECT attribute_id FROM attributes WHERE name = ?", (data['attribute'],))
        result = cursor.fetchone()
        if result:
            attr_id = result[0]
            
            if data.get('subskill'):
                cursor.execute("SELECT subskill_id FROM subskills WHERE attribute_id = ? AND name = ?",
                             (attr_id, data['subskill']))
                result = cursor.fetchone()
                if result:
                    sub_id = result[0]
    
    # Calculate XP based on difficulty
    xp = 0 if data.get('is_negative_habit') else TASK_DIFFICULTIES.get(data.get('difficulty', 'medium'), 25)
    
    cursor.execute("""
        INSERT INTO tasks (date, description, task_type, attribute_id, subskill_id,
                         xp_gained, stress_effect, is_negative_habit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('date', datetime.date.today().isoformat()),
        data['description'],
        data.get('type', 'general'),
        attr_id,
        sub_id,
        xp,
        int(data.get('stress_effect', 0)),
        data.get('is_negative_habit', False)
    ))
    
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    
    return jsonify({'success': True, 'task_id': task_id})

@app.route('/api/complete_task', methods=['POST'])
def api_complete_task():
    data = request.json
    task_id = data.get('task_id')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get task details
    cursor.execute("""
        SELECT attribute_id, subskill_id, xp_gained, stress_effect, is_completed, is_negative_habit, date
        FROM tasks WHERE task_id = ?
    """, (task_id,))
    
    task = cursor.fetchone()
    if not task:
        conn.close()
        return jsonify({'success': False, 'error': 'Task not found'})
    
    if task[4]:  # Already completed
        conn.close()
        return jsonify({'success': False, 'error': 'Task already completed'})
    
    # Mark as completed
    cursor.execute("UPDATE tasks SET is_completed = 1 WHERE task_id = ?", (task_id,))
    
    # Update XP if not negative habit
    if not task[5] and task[2] > 0:
        if task[0]:  # Has attribute
            cursor.execute("UPDATE attributes SET current_xp = current_xp + ? WHERE attribute_id = ?",
                         (task[2], task[0]))
            
            # Check for level up milestone
            cursor.execute("SELECT current_xp FROM attributes WHERE attribute_id = ?", (task[0],))
            new_xp = cursor.fetchone()[0]
            new_level = calculate_level_from_exp(new_xp)
            old_level = calculate_level_from_exp(new_xp - task[2])
            
            if new_level > old_level:
                cursor.execute("SELECT name FROM attributes WHERE attribute_id = ?", (task[0],))
                attr_name = cursor.fetchone()[0]
                cursor.execute("""
                    INSERT INTO milestones (date, title, description, attribute_id, achievement_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (task[6], f"Level Up: {attr_name}", f"Reached level {new_level} in {attr_name}!", task[0], 'level_up'))
                
        if task[1]:  # Has subskill
            cursor.execute("UPDATE subskills SET current_xp = current_xp + ? WHERE subskill_id = ?",
                         (task[2], task[1]))
    
    # Update stress
    if task[3] != 0:
        cursor.execute("UPDATE character_stats SET value = MAX(0, value + ?) WHERE stat_name = 'Stress'",
                     (task[3],))
    
    # Update daily stats
    today = datetime.date.today().isoformat()
    cursor.execute("INSERT OR IGNORE INTO daily_stats (date) VALUES (?)", (today,))
    cursor.execute("""
        UPDATE daily_stats 
        SET tasks_completed = tasks_completed + 1,
            total_xp_gained = total_xp_gained + ?
        WHERE date = ?
    """, (task[2] if not task[5] else 0, today))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/delete_task', methods=['POST'])
def api_delete_task():
    data = request.json
    task_id = data.get('task_id')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get task details first
    cursor.execute("""
        SELECT attribute_id, subskill_id, xp_gained, is_completed, is_negative_habit
        FROM tasks WHERE task_id = ?
    """, (task_id,))
    
    task = cursor.fetchone()
    if not task:
        conn.close()
        return jsonify({'success': False, 'error': 'Task not found'})
    
    # If completed and gave XP, subtract it back
    if task[3] and not task[4] and task[2] > 0:  # was completed, not negative, had XP
        if task[0]:  # Has attribute
            cursor.execute("UPDATE attributes SET current_xp = MAX(0, current_xp - ?) WHERE attribute_id = ?",
                         (task[2], task[0]))
        if task[1]:  # Has subskill
            cursor.execute("UPDATE subskills SET current_xp = MAX(0, current_xp - ?) WHERE subskill_id = ?",
                         (task[2], task[1]))
    
    # Delete the task
    cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/stats')
def api_get_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    stats = {}
    
    # Get character stats
    cursor.execute("SELECT stat_name, value FROM character_stats")
    for row in cursor.fetchall():
        stats[row[0]] = row[1]
    
    # Get total completed tasks
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE is_completed = 1")
    stats['Total Tasks Completed'] = cursor.fetchone()[0]
    
    # Get total XP
    cursor.execute("SELECT SUM(current_xp) FROM attributes")
    stats['Total XP'] = cursor.fetchone()[0] or 0
    
    # Get active/completed quest counts
    cursor.execute("SELECT COUNT(*) FROM quests WHERE status = 'Active'")
    stats['Active Quests'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM quests WHERE status = 'Completed'")
    stats['Completed Quests'] = cursor.fetchone()[0]
    
    conn.close()
    return jsonify(stats)

@app.route('/api/milestones')
def api_get_milestones():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get total count
    cursor.execute("SELECT COUNT(*) FROM milestones")
    total = cursor.fetchone()[0]
    
    # Get paginated milestones
    offset = (page - 1) * per_page
    cursor.execute("""
        SELECT m.milestone_id, m.date, m.title, m.description, m.achievement_type, a.name
        FROM milestones m
        LEFT JOIN attributes a ON m.attribute_id = a.attribute_id
        ORDER BY m.date DESC, m.milestone_id DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    
    milestones = []
    for row in cursor.fetchall():
        milestones.append({
            'id': row[0],
            'date': row[1],
            'title': row[2],
            'description': row[3],
            'type': row[4],
            'attribute': row[5]
        })
    
    conn.close()
    
    return jsonify({
        'milestones': milestones,
        'current_page': page,
        'pages': math.ceil(total / per_page),
        'total': total
    })

@app.route('/api/delete_milestone', methods=['POST'])
def api_delete_milestone():
    data = request.json
    milestone_id = data.get('milestone_id')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM milestones WHERE milestone_id = ?", (milestone_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return jsonify({'success': success})

@app.route('/api/narrative')
def api_get_narrative():
    date = request.args.get('date', datetime.date.today().isoformat())
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT narrative FROM daily_narratives WHERE date = ?", (date,))
    result = cursor.fetchone()
    conn.close()
    
    narrative = result[0] if result else "No adventure recorded for this day yet..."
    
    return jsonify({
        'date': date,
        'narrative': narrative
    })

@app.route('/api/generate_narrative', methods=['POST'])
def api_generate_narrative():
    data = request.json
    api_key = data.get('api_key')
    date = data.get('date', datetime.date.today().isoformat())
    
    if not api_key:
        return jsonify({'error': 'API key required'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get completed tasks for context
    cursor.execute("""
        SELECT t.description, a.name 
        FROM tasks t
        LEFT JOIN attributes a ON t.attribute_id = a.attribute_id
        WHERE t.date = ? AND t.is_completed = 1 AND t.is_negative_habit = 0
    """, (date,))
    
    completed_tasks = cursor.fetchall()
    
    # Generate narrative
    if completed_tasks:
        task_summary = ", ".join([f"{task[0]} ({task[1] or 'General'})" for task in completed_tasks])
        prompt = f"Write a short, epic D&D-style narrative (150 words max) about an adventurer who accomplished: {task_summary}. Make it motivational and heroic."
    else:
        prompt = f"Write a short D&D-style narrative (150 words max) about a day of rest and preparation for an adventurer. Make it contemplative but hopeful."
    
    narrative = generate_ai_response(prompt, 
                                   "You are a D&D dungeon master creating daily adventure narratives.",
                                   api_key)
    
    # Save narrative
    cursor.execute("INSERT OR REPLACE INTO daily_narratives (date, narrative) VALUES (?, ?)",
                  (date, narrative))
    conn.commit()
    conn.close()
    
    return jsonify({'narrative': narrative, 'date': date})

@app.route('/api/narratives')
def api_get_narratives():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 3, type=int)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get total count
    cursor.execute("SELECT COUNT(*) FROM daily_narratives")
    total = cursor.fetchone()[0]
    
    # Get paginated narratives
    offset = (page - 1) * per_page
    cursor.execute("""
        SELECT date, narrative FROM daily_narratives
        ORDER BY date DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    
    narratives = []
    for row in cursor.fetchall():
        narratives.append({
            'date': row[0],
            'narrative': row[1]
        })
    
    conn.close()
    
    return jsonify({
        'narratives': narratives,
        'current_page': page,
        'pages': math.ceil(total / per_page),
        'total': total
    })

@app.route('/api/heatmap')
def api_get_heatmap():
    year = request.args.get('year', datetime.date.today().year, type=int)
    month = request.args.get('month', datetime.date.today().month, type=int)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get daily stats for the month
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
    cursor.execute("""
        SELECT date, COALESCE(tasks_completed, 0), COALESCE(total_xp_gained, 0)
        FROM daily_stats
        WHERE date >= ? AND date < ?
        ORDER BY date
    """, (start_date, end_date))
    
    data = []
    for row in cursor.fetchall():
        data.append({
            'date': row[0],
            'count': row[1],
            'xp': row[2]
        })
    
    conn.close()
    return jsonify(data)

@app.route('/api/attribute_history')
def api_get_attribute_history():
    days = request.args.get('days', 30, type=int)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get date range
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    
    # Get attributes
    cursor.execute("SELECT attribute_id, name FROM attributes ORDER BY name")
    attributes = cursor.fetchall()
    
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
    
    for attr_id, attr_name in attributes:
        levels = []
        running_xp = 0
        
        for date_str in dates:
            # Get XP gained on this date for this attribute
            cursor.execute("""
                SELECT SUM(xp_gained) FROM tasks 
                WHERE attribute_id = ? AND date = ? AND is_completed = 1 AND is_negative_habit = 0
            """, (attr_id, date_str))
            
            daily_xp = cursor.fetchone()[0] or 0
            running_xp += daily_xp
            levels.append(calculate_level_from_exp(running_xp))
        
        result['attributes'][attr_name] = levels
    
    conn.close()
    return jsonify(result)

@app.route('/api/quests')
def api_get_quests():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT quest_id, title, description, difficulty, xp_reward, 
               attribute_focus, start_date, due_date, completed_date, status
        FROM quests
        ORDER BY status = 'Active' DESC, due_date ASC
    """)
    
    quests = []
    for row in cursor.fetchall():
        quests.append({
            'id': row[0],
            'title': row[1],
            'description': row[2],
            'difficulty': row[3],
            'xp_reward': row[4],
            'attribute_focus': row[5],
            'start_date': row[6],
            'due_date': row[7],
            'completed_date': row[8],
            'status': row[9]
        })
    
    conn.close()
    return jsonify(quests)

@app.route('/api/add_quest', methods=['POST'])
def api_add_quest():
    data = request.json
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO quests (title, description, difficulty, xp_reward, attribute_focus, start_date, due_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data['title'],
        data.get('description', ''),
        data.get('difficulty', 'Medium'),
        data.get('xp_reward', 100),
        data.get('attribute_focus', ''),
        datetime.date.today().isoformat(),
        data.get('due_date')
    ))
    
    quest_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'quest_id': quest_id})

@app.route('/api/complete_quest', methods=['POST'])
def api_complete_quest():
    data = request.json
    quest_id = data.get('quest_id')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get quest details
    cursor.execute("""
        SELECT title, xp_reward, attribute_focus, status
        FROM quests WHERE quest_id = ?
    """, (quest_id,))
    
    quest = cursor.fetchone()
    if not quest or quest[3] == 'Completed':
        conn.close()
        return jsonify({'success': False, 'error': 'Quest not found or already completed'})
    
    # Mark as completed
    today = datetime.date.today().isoformat()
    cursor.execute("""
        UPDATE quests SET status = 'Completed', completed_date = ?
        WHERE quest_id = ?
    """, (today, quest_id))
    
    # Add XP to attribute if specified
    if quest[2]:  # attribute_focus
        cursor.execute("SELECT attribute_id FROM attributes WHERE name = ?", (quest[2],))
        attr_result = cursor.fetchone()
        if attr_result:
            cursor.execute("UPDATE attributes SET current_xp = current_xp + ? WHERE attribute_id = ?",
                         (quest[1], attr_result[0]))
    
    # Add milestone
    cursor.execute("""
        INSERT INTO milestones (date, title, description, achievement_type)
        VALUES (?, ?, ?, ?)
    """, (today, f"Quest Completed: {quest[0]}", f"Successfully completed the quest '{quest[0]}' and earned {quest[1]} XP!", 'quest'))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/generate_quest', methods=['POST'])
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

@app.route('/api/recurring_tasks', methods=['GET'])
def api_get_recurring_tasks():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT rt.recurring_task_id, rt.description, a.name as attribute_name, 
               s.name as subskill_name, rt.xp_value, rt.stress_effect, 
               rt.is_negative_habit, rt.is_active, rt.last_added_date
        FROM recurring_tasks rt
        LEFT JOIN attributes a ON rt.attribute_id = a.attribute_id
        LEFT JOIN subskills s ON rt.subskill_id = s.subskill_id
        ORDER BY rt.is_active DESC, rt.description
    """)
    
    tasks = []
    for row in cursor.fetchall():
        tasks.append({
            'recurring_task_id': row[0],
            'description': row[1],
            'attribute_name': row[2],
            'subskill_name': row[3],
            'xp_value': row[4],
            'stress_effect': row[5],
            'is_negative_habit': bool(row[6]),
            'is_active': bool(row[7]),
            'last_added_date': row[8]
        })
    
    conn.close()
    return jsonify(tasks)

@app.route('/api/recurring_tasks', methods=['POST'])
def api_add_recurring_task():
    data = request.json
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get attribute and subskill IDs
    attr_id = None
    sub_id = None
    
    if data.get('attribute'):
        cursor.execute("SELECT attribute_id FROM attributes WHERE name = ?", (data['attribute'],))
        result = cursor.fetchone()
        if result:
            attr_id = result[0]
    
    # Calculate XP based on difficulty
    xp = 0 if data.get('is_negative_habit') else TASK_DIFFICULTIES.get(data.get('difficulty', 'medium'), 25)
    
    cursor.execute("""
        INSERT INTO recurring_tasks (description, attribute_id, subskill_id, xp_value, 
                                   stress_effect, is_negative_habit, start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data['description'],
        attr_id,
        sub_id,
        xp,
        int(data.get('stress_effect', 0)),
        data.get('is_negative_habit', False),
        datetime.date.today().isoformat()
    ))
    
    rt_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'recurring_task_id': rt_id})

@app.route('/api/recurring_tasks/<int:rt_id>', methods=['DELETE'])
def api_delete_recurring_task(rt_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recurring_tasks WHERE recurring_task_id = ?", (rt_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return jsonify({'success': success})

@app.route('/api/recurring_tasks/<int:rt_id>/toggle_active', methods=['POST'])
def api_toggle_recurring_task(rt_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_active FROM recurring_tasks WHERE recurring_task_id = ?", (rt_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return jsonify({'success': False, 'error': 'Recurring task not found'})
    
    new_state = not result[0]
    cursor.execute("UPDATE recurring_tasks SET is_active = ? WHERE recurring_task_id = ?", 
                  (new_state, rt_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'is_active': new_state})

@app.route('/api/reset_day', methods=['POST'])
def api_reset_day():
    data = request.json
    date = data.get('date', datetime.date.today().isoformat())
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get tasks to be deleted (for XP rollback)
        cursor.execute("""
            SELECT attribute_id, subskill_id, xp_gained 
            FROM tasks 
            WHERE date = ? AND is_completed = 1 AND is_negative_habit = 0
        """, (date,))
        
        completed_tasks = cursor.fetchall()
        
        # Rollback XP
        for attr_id, sub_id, xp in completed_tasks:
            if attr_id and xp > 0:
                cursor.execute("UPDATE attributes SET current_xp = MAX(0, current_xp - ?) WHERE attribute_id = ?",
                             (xp, attr_id))
            if sub_id and xp > 0:
                cursor.execute("UPDATE subskills SET current_xp = MAX(0, current_xp - ?) WHERE subskill_id = ?",
                             (xp, sub_id))
        
        # Delete tasks
        cursor.execute("DELETE FROM tasks WHERE date = ?", (date,))
        tasks_deleted = cursor.rowcount
        
        # Reset daily stats
        cursor.execute("DELETE FROM daily_stats WHERE date = ?", (date,))
        
        # Delete narrative
        cursor.execute("DELETE FROM daily_narratives WHERE date = ?", (date,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'date': date,
            'tasks_deleted': tasks_deleted
        })
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
