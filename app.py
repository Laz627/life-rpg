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
    
    # Create tables
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
        attr_id = cursor.fetchone()[0]
        
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
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",  # Using cheaper model
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
    
    try:
        openai.api_key = api_key
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/attributes')
def api_get_attributes():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT attribute_id, name, current_xp FROM attributes ORDER BY name")
    attributes = []
    
    for row in cursor.fetchall():
        attr_id, name, xp = row
        level = calculate_level_from_exp(xp)
        
        # Get subskills
        cursor.execute("SELECT subskill_id, name, current_xp FROM subskills WHERE attribute_id = ?", (attr_id,))
        subskills = []
        for sub_row in cursor.fetchall():
            sub_id, sub_name, sub_xp = sub_row
            sub_level = calculate_level_from_exp(sub_xp)
            subskills.append({
                'id': sub_id,
                'name': sub_name,
                'level': sub_level,
                'total_xp': sub_xp,
                'xp_progress': sub_xp - calculate_exp_for_level(sub_level),
                'xp_needed': calculate_exp_for_level(sub_level + 1) - calculate_exp_for_level(sub_level)
            })
        
        attributes.append({
            'id': attr_id,
            'name': name,
            'level': level,
            'total_xp': xp,
            'xp_progress': xp - calculate_exp_for_level(level),
            'xp_needed': calculate_exp_for_level(level + 1) - calculate_exp_for_level(level),
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
    conn.close()
    
    return jsonify({'success': True, 'task_id': cursor.lastrowid})

@app.route('/api/complete_task', methods=['POST'])
def api_complete_task():
    data = request.json
    task_id = data.get('task_id')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get task details
    cursor.execute("""
        SELECT attribute_id, subskill_id, xp_gained, stress_effect, is_completed, is_negative_habit
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
        if task[1]:  # Has subskill
            cursor.execute("UPDATE subskills SET current_xp = current_xp + ? WHERE subskill_id = ?",
                         (task[2], task[1]))
    
    # Update stress
    if task[3] != 0:
        cursor.execute("UPDATE character_stats SET value = value + ? WHERE stat_name = 'Stress'",
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
    
    conn.close()
    return jsonify(stats)

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
        WHERE t.date = ? AND t.is_completed = 1
    """, (date,))
    
    completed_tasks = cursor.fetchall()
    
    # Generate narrative
    prompt = f"Create a short D&D-style narrative for a day where the adventurer completed these tasks: {completed_tasks}. Make it epic and motivational. Maximum 150 words."
    
    narrative = generate_ai_response(prompt, 
                                   "You are a D&D dungeon master creating daily adventure narratives.",
                                   api_key)
    
    # Save narrative
    cursor.execute("INSERT OR REPLACE INTO daily_narratives (date, narrative) VALUES (?, ?)",
                  (date, narrative))
    conn.commit()
    conn.close()
    
    return jsonify({'narrative': narrative})

@app.route('/api/quests')
def api_get_quests():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT quest_id, title, description, difficulty, xp_reward, 
               attribute_focus, start_date, due_date, status
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
            'status': row[8]
        })
    
    conn.close()
    return jsonify(quests)

@app.route('/api/generate_quest', methods=['POST'])
def api_generate_quest():
    data = request.json
    api_key = data.get('api_key')
    
    if not api_key:
        return jsonify({'error': 'API key required'}), 400
    
    attribute = data.get('attribute_focus', random.choice(list(ATTRIBUTES.keys())))
    difficulty = data.get('difficulty', random.choice(QUEST_DIFFICULTIES))
    
    prompt = f"Create a self-improvement quest focusing on {attribute} with {difficulty} difficulty. Format: Title: [title]\nDescription: [description in 50 words or less]"
    
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
    
    return jsonify({
        'title': title,
        'description': description,
        'difficulty': difficulty,
        'attribute_focus': attribute,
        'xp_reward': xp_rewards.get(difficulty, 100)
    })

@app.route('/api/recurring_tasks')
def api_get_recurring_tasks():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT rt.recurring_task_id, rt.description, a.name as attribute_name, 
               s.name as subskill_name, rt.xp_value, rt.stress_effect, 
               rt.is_negative_habit, rt.is_active
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
            'is_active': bool(row[7])
        })
    
    conn.close()
    return jsonify(tasks)

if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
