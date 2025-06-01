// Global variables
let currentDate = new Date().toISOString().split('T')[0];
let attributes = [];

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

async function initializeApp() {
    // Initialize database
    await fetch('/api/init');
    
    // Check for API key
    const apiKey = localStorage.getItem('openai_api_key');
    if (!apiKey) {
        document.getElementById('apiKeyModal').style.display = 'block';
    }
    
    // Load initial data
    updateDateDisplay();
    loadAttributes();
    loadTasks();
    loadStats();
    loadQuests();
    
    // Set up intervals
    setInterval(updateDateDisplay, 60000); // Update every minute
}

// API Key Management
function saveApiKey() {
    const apiKey = document.getElementById('apiKeyInput').value;
    if (!apiKey) {
        alert('Please enter an API key');
        return;
    }
    
    // Test the API key
    fetch('/api/test_api_key', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({api_key: apiKey})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            localStorage.setItem('openai_api_key', apiKey);
            document.getElementById('apiKeyModal').style.display = 'none';
            alert('API key saved successfully!');
            enableAIFeatures();
        } else {
            alert('Invalid API key. Please check and try again.');
        }
    });
}

function skipApiKey() {
    document.getElementById('apiKeyModal').style.display = 'none';
    disableAIFeatures();
}

function enableAIFeatures() {
    document.getElementById('generateQuestBtn').disabled = false;
    document.getElementById('generateNarrativeBtn').disabled = false;
}

function disableAIFeatures() {
    document.getElementById('generateQuestBtn').disabled = true;
    document.getElementById('generateQuestBtn').textContent = 'Generate New Quest (Requires API Key)';
    document.getElementById('generateNarrativeBtn').disabled = true;
    document.getElementById('generateNarrativeBtn').textContent = 'Generate Narrative (Requires API Key)';
}

// Date Management
function updateDateDisplay() {
    const now = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('dateDisplay').textContent = now.toLocaleDateString('en-US', options);
}

// Load Functions
async function loadAttributes() {
    const response = await fetch('/api/attributes');
    attributes = await response.json();
    
    // Update attribute dropdown
    const select = document.getElementById('taskAttribute');
    select.innerHTML = '<option value="">Select Attribute</option>';
    attributes.forEach(attr => {
        const option = document.createElement('option');
        option.value = attr.name;
        option.textContent = `${attr.name} (Lv ${attr.level})`;
        select.appendChild(option);
    });
    
    // Display attributes
    displayAttributes();
}

function displayAttributes() {
    const container = document.getElementById('attributesContent');
    container.innerHTML = '';
    
    attributes.forEach(attr => {
        const progressPercent = (attr.xp_progress / attr.xp_needed) * 100;
        
        const attrHtml = `
            <div class="attribute-item">
                <div class="attribute-header">
                    <h3>${attr.name}</h3>
                    <span class="level-badge">Level ${attr.level}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progressPercent}%"></div>
                </div>
                <div class="xp-text">${attr.xp_progress} / ${attr.xp_needed} XP</div>
            </div>
        `;
        container.innerHTML += attrHtml;
    });
}

async function loadTasks() {
    const response = await fetch(`/api/tasks?date=${currentDate}`);
    const tasks = await response.json();
    
    const container = document.getElementById('tasksList');
    container.innerHTML = '';
    
    // Separate completed and incomplete tasks
    const incompleteTasks = tasks.filter(t => !t.completed);
    const completedTasks = tasks.filter(t => t.completed);
    
    [...incompleteTasks, ...completedTasks].forEach(task => {
        const taskHtml = `
            <div class="task-item ${task.completed ? 'completed' : ''}">
                <div class="task-info">
                    <div class="task-description">${task.description}</div>
                    <div class="task-meta">
                        ${task.attribute || 'No attribute'} 
                        ${task.subskill ? `- ${task.subskill}` : ''} 
                        | ${task.xp} XP
                    </div>
                </div>
                <div class="task-actions">
                    ${!task.completed ? 
                        `<button onclick="completeTask(${task.id})">Complete</button>` : 
                        ''
                    }
                    <button onclick="deleteTask(${task.id})">Delete</button>
                </div>
            </div>
        `;
        container.innerHTML += taskHtml;
    });
}

async function loadStats() {
    const response = await fetch('/api/stats');
    const stats = await response.json();
    
    const container = document.getElementById('statsContent');
    container.innerHTML = `
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-label">Total XP</div>
                <div class="stat-value">${stats['Total XP'] || 0}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Tasks Completed</div>
                <div class="stat-value">${stats['Total Tasks Completed'] || 0}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Stress Level</div>
                <div class="stat-value">${stats['Stress'] || 0}</div>
            </div>
        </div>
    `;
}

async function loadQuests() {
    const response = await fetch('/api/quests');
    const quests = await response.json();
    
    const container = document.getElementById('questsList');
    container.innerHTML = '';
    
    const activeQuests = quests.filter(q => q.status === 'Active');
    
    if (activeQuests.length === 0) {
        container.innerHTML = '<p>No active quests. Generate one!</p>';
        return;
    }
    
    activeQuests.forEach(quest => {
        const questHtml = `
            <div class="quest-item">
                <div class="quest-header">
                    <h4>${quest.title}</h4>
                    <span class="quest-difficulty difficulty-${quest.difficulty}">${quest.difficulty}</span>
                </div>
                <p>${quest.description}</p>
                <div class="quest-meta">
                    <span>${quest.attribute_focus} | ${quest.xp_reward} XP</span>
                    <span>Due: ${quest.due_date || 'No deadline'}</span>
                </div>
            </div>
        `;
        container.innerHTML += questHtml;
    });
}

// Task Functions
async function addTask() {
    const description = document.getElementById('taskDescription').value;
    const attribute = document.getElementById('taskAttribute').value;
    const subskill = document.getElementById('taskSubskill').value;
    const difficulty = document.getElementById('taskDifficulty').value;
    
    if (!description) {
        alert('Please enter a task description');
        return;
    }
    
    const response = await fetch('/api/add_task', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            description,
            attribute,
            subskill,
            difficulty,
            date: currentDate
        })
    });
    
    if (response.ok) {
        document.getElementById('taskDescription').value = '';
        loadTasks();
    }
}

async function completeTask(taskId) {
    const response = await fetch('/api/complete_task', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({task_id: taskId})
    });
    
    if (response.ok) {
        loadTasks();
        loadStats();
        loadAttributes();
    }
}

async function deleteTask(taskId) {
    if (!confirm('Delete this task?')) return;
    
    // For simplicity, we'll just remove from display
    // In a full implementation, you'd add a delete endpoint
    loadTasks();
}

// Update subskills when attribute changes
document.getElementById('taskAttribute').addEventListener('change', function() {
    const selectedAttr = attributes.find(a => a.name === this.value);
    const subskillSelect = document.getElementById('taskSubskill');
    
    subskillSelect.innerHTML = '<option value="">Select Subskill</option>';
    
    if (selectedAttr && selectedAttr.subskills) {
        selectedAttr.subskills.forEach(sub => {
            const option = document.createElement('option');
            option.value = sub.name;
            option.textContent = `${sub.name} (Lv ${sub.level})`;
            subskillSelect.appendChild(option);
        });
    }
});

// AI Functions
async function generateQuest() {
    const apiKey = localStorage.getItem('openai_api_key');
    if (!apiKey) {
        document.getElementById('apiKeyModal').style.display = 'block';
        return;
    }
    
    const btn = document.getElementById('generateQuestBtn');
    btn.disabled = true;
    btn.textContent = 'Generating...';
    
    try {
        const response = await fetch('/api/generate_quest', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({api_key: apiKey})
        });
        
        const quest = await response.json();
        
        if (quest.error) {
            alert('Error generating quest: ' + quest.error);
        } else {
            alert(`New Quest Generated!\n\n${quest.title}\n\n${quest.description}\n\nDifficulty: ${quest.difficulty}\nReward: ${quest.xp_reward} XP`);
            loadQuests();
        }
    } catch (error) {
        alert('Error generating quest');
    }
    
    btn.disabled = false;
    btn.textContent = 'Generate New Quest (AI)';
}

async function generateNarrative() {
    const apiKey = localStorage.getItem('openai_api_key');
    if (!apiKey) {
        document.getElementById('apiKeyModal').style.display = 'block';
        return;
    }
    
    const btn = document.getElementById('generateNarrativeBtn');
    btn.disabled = true;
    btn.textContent = 'Generating...';
    
    try {
        const response = await fetch('/api/generate_narrative', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                api_key: apiKey,
                date: currentDate
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('Error generating narrative: ' + data.error);
        } else {
            document.getElementById('narrativeContent').innerHTML = `<p>${data.narrative}</p>`;
        }
    } catch (error) {
        alert('Error generating narrative');
    }
    
    btn.disabled = false;
    btn.textContent = 'Generate Narrative (AI)';
}

// PWA Support
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js');
}

// Install prompt
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    // Show install button
    const installBtn = document.createElement('button');
    installBtn.className = 'install-button';
    installBtn.textContent = 'Install App';
    installBtn.onclick = async () => {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') {
            installBtn.style.display = 'none';
        }
    };
    document.body.appendChild(installBtn);
    installBtn.style.display = 'block';
});
