// --- Global State Variables ---
let currentSelectedDate = new Date().toISOString().split('T')[0];
let attributes = [];
let tasks = [];
let recurringTasks = [];
let characterStats = {};
let quests = [];
let milestones = { data: [], page: 1, totalPages: 1, perPage: 5 };
let narratives = { data: [], page: 1, totalPages: 1, perPage: 3 };
let attributeHistoryChart = null;
let heatmapCurrentDate = new Date(); // For heatmap navigation

// --- DOM Ready Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    checkAPIKey();
    document.getElementById('selected-date').value = currentSelectedDate;
    initializePageData();
    setupEventListeners();
});

function checkAPIKey() {
    const apiKey = localStorage.getItem('openai_api_key');
    if (!apiKey) {
        document.getElementById('apiKeyModal').style.display = 'block';
    } else {
        enableAIFeatures();
    }
}

function enableAIFeatures() {
    const generateBtns = document.querySelectorAll('[id*="generate"], [id*="enhance"]');
    generateBtns.forEach(btn => {
        btn.disabled = false;
        btn.textContent = btn.textContent.replace(' (Requires API Key)', '');
    });
}

function disableAIFeatures() {
    const generateBtns = document.querySelectorAll('[id*="generate"], [id*="enhance"]');
    generateBtns.forEach(btn => {
        btn.disabled = true;
        if (!btn.textContent.includes('(Requires API Key)')) {
            btn.textContent += ' (Requires API Key)';
        }
    });
}

function saveApiKey() {
    const apiKey = document.getElementById('apiKeyInput').value;
    if (!apiKey) {
        alert('Please enter an API key');
        return;
    }
    
    // Test the API key
    apiCall('/api/test_api_key', 'POST', {api_key: apiKey})
    .then(data => {
        if (data && data.success) {
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

async function initializePageData() {
    console.log("Initializing all page data...");
    
    // Fetch in a somewhat logical order, things that populate dropdowns first
    await fetchAndRenderAttributes(); // Attributes needed for dropdowns
    
    // Then fetch other core data
    await fetchAndRenderTasks(currentSelectedDate);
    await fetchAndRenderStats();
    await fetchAndRenderRecurringTasks();
    await fetchAndRenderQuests();
    await fetchAndRenderMilestones(milestones.page);
    await fetchAndRenderDailyNarrative(currentSelectedDate);
    await fetchAndRenderNarrativeHistory(narratives.page);
    await fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1); // Month is 1-indexed for API
    await fetchAndRenderAttributeHistory();
    
    updateHeatmapControlsLabel(); // Set initial heatmap label
}

// --- Event Listener Setup ---
function setupEventListeners() {
    // Date Picker for Tasks and Narratives
    document.getElementById('selected-date').addEventListener('change', handleDateChange);

    // Task Management
    document.getElementById('add-task-btn').addEventListener('click', () => toggleForm('add-task-form-container'));
    document.getElementById('add-task-form').addEventListener('submit', handleAddTask);
    document.getElementById('task-stress').addEventListener('input', (e) => { document.getElementById('task-stress-value-display').textContent = e.target.value; });
    setupRadioGroup('task-type-radio', 'task-difficulty', 'task-stress', 'task-stress-value-display');
    document.getElementById('reset-day-btn').addEventListener('click', handleResetDay);

    // Recurring Task Management
    document.getElementById('add-recurring-task-btn').addEventListener('click', () => toggleForm('add-recurring-task-form-container'));
    document.getElementById('add-recurring-task-form').addEventListener('submit', handleAddRecurringTask);
    document.getElementById('recurring-task-stress').addEventListener('input', (e) => { document.getElementById('recurring-task-stress-value-display').textContent = e.target.value; });
    setupRadioGroup('recurring-task-type-radio', 'recurring-task-difficulty', 'recurring-task-stress', 'recurring-task-stress-value-display');

    // Quest Management
    document.getElementById('add-quest-btn').addEventListener('click', () => toggleForm('add-quest-form-container'));
    document.getElementById('add-quest-form').addEventListener('submit', handleAddQuest);
    document.getElementById('generate-quest-btn').addEventListener('click', handleGenerateQuest);
    document.getElementById('enhance-quest-desc-btn').addEventListener('click', enhanceQuestDescription);
    
    // Narrative Management
    document.getElementById('refresh-narrative-btn').addEventListener('click', () => fetchAndRenderDailyNarrative(currentSelectedDate, true)); // true to force regeneration

    // Heatmap Navigation
    document.getElementById('prev-month-heatmap').addEventListener('click', () => navigateHeatmapMonth(-1));
    document.getElementById('next-month-heatmap').addEventListener('click', () => navigateHeatmapMonth(1));
}

function toggleForm(formContainerId) {
    const container = document.getElementById(formContainerId);
    container.style.display = container.style.display === 'none' ? 'block' : 'none';
}

function setupRadioGroup(groupId, difficultySelectId, stressSliderId, stressValueDisplayId) {
    const group = document.getElementById(groupId);
    if (!group) return;
    const options = group.querySelectorAll('.radio-option');
    options.forEach(option => {
        option.addEventListener('click', () => {
            options.forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');
            
            const isNegative = option.dataset.value === 'negative';
            const difficultySelect = document.getElementById(difficultySelectId);
            const stressSlider = document.getElementById(stressSliderId);
            const stressValueDisplay = document.getElementById(stressValueDisplayId);

            if (difficultySelect) difficultySelect.disabled = isNegative;
            if (stressSlider && stressValueDisplay) {
                let currentStress = parseInt(stressSlider.value);
                if (isNegative) {
                    stressSlider.value = Math.abs(currentStress) || 3;
                } else {
                    stressSlider.value = -(Math.abs(currentStress) || 3);
                }
                stressValueDisplay.textContent = stressSlider.value;
            }
        });
    });
    // Initialize by clicking the first selected or first overall if none are pre-selected
    const selectedOption = group.querySelector('.radio-option.selected') || options[0];
    if (selectedOption) selectedOption.click();
}

// --- Enhanced Features ---

// Enhanced quest description
async function enhanceQuestDescription() {
    const apiKey = localStorage.getItem('openai_api_key');
    if (!apiKey) {
        document.getElementById('apiKeyModal').style.display = 'block';
        return;
    }
    
    const descriptionField = document.getElementById('quest-description');
    const originalDescription = descriptionField.value.trim();
    
    if (!originalDescription) {
        alert('Please enter a description first');
        return;
    }
    
    const enhanceBtn = document.getElementById('enhance-quest-desc-btn');
    enhanceBtn.disabled = true;
    enhanceBtn.textContent = 'Enhancing...';
    
    try {
        const response = await apiCall('/api/enhance_quest_description', 'POST', {
            api_key: apiKey,
            description: originalDescription
        });
        
        if (response && response.enhanced_description) {
            descriptionField.value = response.enhanced_description;
        }
    } catch (error) {
        console.error('Error enhancing description:', error);
    }
    
    enhanceBtn.disabled = false;
    enhanceBtn.textContent = '✨ Enhance Description (AI)';
}

// Complete negative habit with Yes/No option
async function completeNegativeHabit(taskId, didNegative) {
    const result = await apiCall('/api/complete_negative_habit', 'POST', { 
        task_id: taskId, 
        did_negative: didNegative 
    });
    
    if (result && result.success) {
        await fetchAndRenderTasks(currentSelectedDate);
        await fetchAndRenderAttributes();
        await fetchAndRenderStats();
        await fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1);
        
        // Show feedback message
        const message = didNegative ? 
            "Habit tracked. Don't worry, tomorrow is a new opportunity!" : 
            "Great job avoiding that habit! You earned bonus XP!";
        
        setTimeout(() => alert(message), 100);
        
        // Potentially fetch milestones if completion could trigger one
        if (Math.random() < 0.2) {
           await fetchAndRenderMilestones(milestones.page);
        }
    }
}

// Skip task function
async function skipTask(taskId) {
    if (!confirm('Mark this task as skipped? It will not count towards your progress.')) return;
    
    const result = await apiCall('/api/skip_task', 'POST', { task_id: taskId });
    if (result && result.success) {
        await fetchAndRenderTasks(currentSelectedDate);
        await fetchAndRenderStats();
    }
}

// --- Event Handlers ---
async function handleDateChange(e) {
    currentSelectedDate = e.target.value;
    const isToday = currentSelectedDate === new Date().toISOString().split('T')[0];
    
    document.getElementById('tasks-card-header').textContent = isToday ? "Today's Tasks" : `Tasks for ${currentSelectedDate}`;
    document.getElementById('narrative-card-header').textContent = isToday ? "Adventure Log" : `Log for ${currentSelectedDate}`;
    document.getElementById('daily-narrative-header').textContent = isToday ? "Today's Adventure" : `Adventure for ${currentSelectedDate}`;

    await fetchAndRenderTasks(currentSelectedDate);
    await fetchAndRenderDailyNarrative(currentSelectedDate);
}

async function handleAddTask(event) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        description: form.querySelector('#task-description').value,
        attribute: form.querySelector('#task-attribute').value,
        difficulty: form.querySelector('#task-difficulty').value,
        stress_effect: parseInt(form.querySelector('#task-stress').value),
        is_negative_habit: form.querySelector('#task-type-radio .selected').dataset.value === 'negative',
        date: currentSelectedDate
    };
    const result = await apiCall('/api/add_task', 'POST', payload);
    if (result && result.success) {
        form.reset();
        setupRadioGroup('task-type-radio', 'task-difficulty', 'task-stress', 'task-stress-value-display'); // Re-init radio
        toggleForm('add-task-form-container');
        await fetchAndRenderTasks(currentSelectedDate);
        if (!payload.is_negative_habit && payload.attribute) await fetchAndRenderAttributes(); // Only if XP might change
        await fetchAndRenderStats();
        await fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1);
    }
}

async function handleResetDay() {
    if (!confirm(`Are you sure you want to reset all data for ${currentSelectedDate}? This action cannot be undone.`)) return;
    const result = await apiCall('/api/reset_day', 'POST', { date: currentSelectedDate });
    if (result && result.success) {
        alert(`Day ${result.date} has been reset. Tasks deleted: ${result.tasks_deleted}.`);
        await initializePageData(); // Full refresh needed as many things could change
    }
}

async function handleAddRecurringTask(event) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        description: form.querySelector('#recurring-task-description').value,
        attribute: form.querySelector('#recurring-task-attribute').value,
        difficulty: form.querySelector('#recurring-task-difficulty').value,
        stress_effect: parseInt(form.querySelector('#recurring-task-stress').value),
        is_negative_habit: form.querySelector('#recurring-task-type-radio .selected').dataset.value === 'negative',
    };
    const result = await apiCall('/api/recurring_tasks', 'POST', payload);
    if (result && result.success) {
        form.reset();
        setupRadioGroup('recurring-task-type-radio', 'recurring-task-difficulty', 'recurring-task-stress', 'recurring-task-stress-value-display');
        toggleForm('add-recurring-task-form-container');
        await fetchAndRenderRecurringTasks();
        await fetchAndRenderTasks(currentSelectedDate); // Refresh tasks, new recurring might appear
    }
}

async function handleAddQuest(event) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        title: form.querySelector('#quest-title').value,
        description: form.querySelector('#quest-description').value,
        difficulty: form.querySelector('#quest-difficulty').value,
        attribute_focus: form.querySelector('#quest-attribute').value,
        due_date: form.querySelector('#quest-due-date').value || null,
        // XP reward is typically set by difficulty on backend or via AI
    };
    // Add XP based on difficulty for manual quests
    const diffToXp = {"Easy": 50, "Medium": 100, "Hard": 175, "Epic": 250};
    payload.xp_reward = diffToXp[payload.difficulty] || 100;

    const result = await apiCall('/api/add_quest', 'POST', payload);
    if (result && result.success) {
        form.reset();
        toggleForm('add-quest-form-container');
        await fetchAndRenderQuests();
        await fetchAndRenderStats(); // Active quest count changes
    }
}

async function handleGenerateQuest() {
    const apiKey = localStorage.getItem('openai_api_key');
    if (!apiKey) {
        document.getElementById('apiKeyModal').style.display = 'block';
        return;
    }
    
    const form = document.getElementById('add-quest-form');
    const attribute = form.querySelector('#quest-attribute').value;
    const difficulty = form.querySelector('#quest-difficulty').value;
    const questData = await apiCall('/api/generate_quest', 'POST', { 
        attribute_focus: attribute, 
        difficulty: difficulty,
        api_key: apiKey 
    });
    if (questData) {
        form.querySelector('#quest-title').value = questData.title || '';
        form.querySelector('#quest-description').value = questData.description || '';
        if (questData.difficulty) form.querySelector('#quest-difficulty').value = questData.difficulty;
        if (questData.attribute_focus) form.querySelector('#quest-attribute').value = questData.attribute_focus;
        if (questData.due_date) form.querySelector('#quest-due-date').value = questData.due_date;
    }
}

// --- Action Functions (called from rendered elements) ---
async function completeTask(taskId) {
    const taskElement = document.querySelector(`button[onclick*="completeTask(${taskId})"]`)?.closest('.task-item');
    if (taskElement) taskElement.style.opacity = '0.5';

    const result = await apiCall('/api/complete_task', 'POST', { task_id: taskId });
    if (result && result.success) {
        await fetchAndRenderTasks(currentSelectedDate);
        await fetchAndRenderAttributes();
        await fetchAndRenderStats();
        await fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1);
        // Potentially fetch milestones if completion could trigger one
        if (Math.random() < 0.2) { // 20% chance, or on specific conditions
           await fetchAndRenderMilestones(milestones.page);
        }
    } else {
        if (taskElement) taskElement.style.opacity = '1';
        // Error already alerted by apiCall
    }
}

async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) return;
    const result = await apiCall('/api/delete_task', 'POST', { task_id: taskId });
    if (result && result.success) {
        await fetchAndRenderTasks(currentSelectedDate);
        // If task was completed, attributes and stats might need refresh
        const deletedTask = tasks.find(t => t.id === taskId); // Requires tasks to be up-to-date or passed
        if (deletedTask && deletedTask.completed && !deletedTask.is_negative_habit) {
            await fetchAndRenderAttributes();
        }
        await fetchAndRenderStats();
        await fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1);
    }
}

async function deleteRecurringTask(rtId) {
    if (!confirm('Delete this recurring habit permanently? This will not delete already generated tasks.')) return;
    const result = await apiCall(`/api/recurring_tasks/${rtId}`, 'DELETE');
    if (result && result.success) {
        await fetchAndRenderRecurringTasks();
        // No need to refresh daily tasks unless backend deletes future generated ones
    }
}

async function toggleRecurringActive(rtId) {
    const result = await apiCall(`/api/recurring_tasks/${rtId}/toggle_active`, 'POST');
    if (result && result.success) {
        await fetchAndRenderRecurringTasks();
        // Refresh tasks for current day as it might add/remove a task if today is affected
        await fetchAndRenderTasks(currentSelectedDate);
    }
}

async function completeQuest(questId) {
    if (!confirm('Mark this quest as completed?')) return;
    const result = await apiCall('/api/complete_quest', 'POST', { quest_id: questId });
    if (result && result.success) {
        await fetchAndRenderQuests();
        await fetchAndRenderAttributes(); // XP from quest
        await fetchAndRenderStats();      // Quest counts, XP
        await fetchAndRenderMilestones(milestones.page); // Quest completion is a milestone
        await fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1);
    }
}

async function deleteMilestone(milestoneId) {
    if (!confirm('Are you sure you want to delete this achievement?')) return;
    const result = await apiCall('/api/delete_milestone', 'POST', { milestone_id: milestoneId });
    if (result && result.success) {
        await fetchAndRenderMilestones(milestones.page);
    }
}

// --- API Call Wrapper ---
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = { method, headers: {} };
    if (body) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
    }
    try {
        const response = await fetch(endpoint, options);
        const responseData = await response.json(); // Try to parse JSON regardless of ok status
        if (!response.ok) {
            console.error(`API Error (${response.status}) ${endpoint}:`, responseData);
            alert(`Error: ${responseData.error || responseData.message || response.statusText}`);
            return null;
        }
        return responseData;
    } catch (error) {
        console.error('Fetch API Error:', error, 'Endpoint:', endpoint);
        alert('A network or unexpected error occurred. Please check the console.');
        return null;
    }
}

// --- Fetch and Render Specific Data Sections ---
async function fetchAndRenderAttributes() {
    attributes = await apiCall('/api/attributes') || [];
    renderAttributes();
    populateAttributeDropdowns();
}

async function fetchAndRenderTasks(date) {
    tasks = await apiCall(`/api/tasks?date=${date}`) || [];
    renderTasks(date);
}

async function fetchAndRenderStats() {
    characterStats = await apiCall('/api/stats') || {};
    renderCharacterStats();
}

async function fetchAndRenderRecurringTasks() {
    recurringTasks = await apiCall('/api/recurring_tasks') || [];
    renderRecurringTasks();
}

async function fetchAndRenderQuests() {
    quests = await apiCall('/api/quests') || [];
    renderQuests();
}

async function fetchAndRenderMilestones(page) {
    const data = await apiCall(`/api/milestones?page=${page}&per_page=${milestones.perPage}`);
    if (data) {
        milestones.data = data.milestones;
        milestones.page = data.current_page;
        milestones.totalPages = data.pages;
        renderMilestones();
        renderPagination('milestones-pagination', 'milestones-pagination-info', milestones, fetchAndRenderMilestones);
    }
}

async function fetchAndRenderDailyNarrative(date, forceRegenerate = false) {
    const apiKey = localStorage.getItem('openai_api_key');
    let data;
    
    if (forceRegenerate && apiKey) {
        data = await apiCall('/api/generate_narrative', 'POST', { date, api_key: apiKey });
    } else {
        data = await apiCall(`/api/narrative?date=${date}`);
    }
    
    if (data) {
        renderDailyNarrative(data.narrative, data.date || date);
        if (forceRegenerate) { // If regenerated, refresh history
            await fetchAndRenderNarrativeHistory(1);
        }
    }
}

async function fetchAndRenderNarrativeHistory(page) {
    const data = await apiCall(`/api/narratives?page=${page}&per_page=${narratives.perPage}`);
    if (data) {
        narratives.data = data.narratives;
        narratives.page = data.current_page;
        narratives.totalPages = data.pages;
        renderNarrativeHistory();
        renderPagination('narratives-pagination', 'narratives-pagination-info', narratives, fetchAndRenderNarrativeHistory);
    }
}

async function fetchAndRenderHeatmap(year, month) { // month is 1-indexed
    const data = await apiCall(`/api/heatmap?year=${year}&month=${month}`);
    if (data) {
        renderHeatmap(year, month, data);
    }
}

async function fetchAndRenderAttributeHistory() {
    const data = await apiCall('/api/attribute_history?days=30'); // Fetch last 30 days
    if (data) {
        renderAttributeHistory(data);
    }
}

// --- DOM Rendering Functions ---
function renderAttributes() {
    const container = document.getElementById('attributes-container');
    container.innerHTML = '';
    if (!attributes || attributes.length === 0) {
        container.innerHTML = '<p>No attributes data.</p>'; return;
    }
    attributes.forEach(attr => {
        const attrEl = document.createElement('div');
        attrEl.className = 'attribute-progress';
        attrEl.innerHTML = `
            <div>
                <span>${attr.name}</span>
                <span class="attribute-level">Lvl ${attr.level}</span>
            </div>
            <div class="progress-bar">
                <div class="progress-bar-fill" style="width: ${attr.progress_percent}%" title="${attr.xp_progress}/${attr.xp_needed} XP">${Math.round(attr.progress_percent)}%</div>
            </div>
            <small>Total XP: ${attr.total_xp}</small>
        `;
        if (attr.subskills && attr.subskills.length > 0) {
            attr.subskills.filter(sub => sub.total_xp > 0).forEach(sub => { // Only show subskills with XP
                const subEl = document.createElement('div');
                subEl.className = 'subskill-progress';
                subEl.innerHTML = `
                    <div>
                        <span>${sub.name}</span>
                        <span class="subskill-level">Lvl ${sub.level}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-bar-fill" style="width: ${sub.progress_percent}%" title="${sub.xp_progress}/${sub.xp_needed} XP">${Math.round(sub.progress_percent)}%</div>
                    </div>
                `;
                attrEl.appendChild(subEl);
            });
        }
        container.appendChild(attrEl);
    });
}

function renderTasks(dateToList = currentSelectedDate) {
    const container = document.getElementById('task-list');
    container.innerHTML = '';

    if (!tasks || tasks.length === 0) {
        container.innerHTML = '<li>No tasks for this day.</li>'; 
        return;
    }
    
    tasks.forEach(task => {
        const taskEl = document.createElement('li');
        let taskClasses = 'task-item';
        
        if (task.completed) taskClasses += ' task-completed';
        if (task.skipped) taskClasses += ' task-skipped';
        if (task.is_negative_habit) taskClasses += ' negative-habit';
        
        taskEl.className = taskClasses;
        
        let attributeText = task.attribute ? `[${task.attribute}${task.subskill ? ` → ${task.subskill}`: ''}]` : '';
        let xpText = task.is_negative_habit ? '' : `(${task.xp} XP)`;
        
        let actionButtons = '';
        
        if (task.completed) {
            actionButtons = '<span class="completion-status">✓ Done!</span>';
        } else if (task.skipped) {
            actionButtons = '<span class="completion-status">⏭ Skipped</span>';
        } else if (task.is_negative_habit) {
            // Special buttons for negative habits
            actionButtons = `
                <div class="task-actions negative-habit-actions">
                    <button onclick="completeNegativeHabit(${task.id}, true)" class="btn-danger btn-small">Yes, I did it</button>
                    <button onclick="completeNegativeHabit(${task.id}, false)" class="btn-success btn-small">No, I avoided it</button>
                </div>
            `;
        } else {
            // Regular task buttons
            actionButtons = `
                <button onclick="completeTask(${task.id})" class="btn-success btn-small">✓ Complete</button>
                <button onclick="skipTask(${task.id})" class="btn-warning btn-small">⏭ Skip</button>
            `;
        }
        
        taskEl.innerHTML = `
            <div>
                ${task.description} ${attributeText} ${xpText}
                <small>Stress: ${task.stress_effect > 0 ? '+' : ''}${task.stress_effect}</small>
            </div>
            <div class="task-actions">
                ${actionButtons}
                <button onclick="deleteTask(${task.id})" class="btn-danger btn-small">🗑 Delete</button>
            </div>
        `;
        container.appendChild(taskEl);
    });
}

function renderCharacterStats() {
    const container = document.getElementById('character-stats');
    container.innerHTML = '';
    const levelDisplay = document.getElementById('character-level');

    if (Object.keys(characterStats).length === 0) {
        container.innerHTML = '<p>Loading stats...</p>'; 
        levelDisplay.textContent = 'Level ?';
        return;
    }
    
    const totalXp = characterStats['Total XP'] || 0;
    const overallLevel = totalXp <= 0 ? 1 : Math.floor(1 + Math.pow(totalXp / 100, 1/2.2));
    levelDisplay.textContent = `Level ${overallLevel}`;

    // Create stats in a specific order
    const statOrder = [
        'Total Tasks Completed',
        'Tasks Remaining Today', 
        'Tasks Skipped Today',
        'Negative Habits Completed',
        'Total XP',
        'Active Quests',
        'Completed Quests'
    ];

    statOrder.forEach(statName => {
        if (characterStats.hasOwnProperty(statName)) {
            const statEl = document.createElement('div');
            statEl.className = 'stat-entry';
            
            // Highlight remaining tasks in red if > 0
            let statValue = characterStats[statName];
            let style = '';
            if (statName === 'Tasks Remaining Today' && statValue > 0) {
                style = ' style="color: var(--negative-color); font-weight: bold;"';
            }
            
            statEl.innerHTML = `<strong${style}>${statName.replace(/([A-Z])/g, ' $1').trim()}:</strong> <span${style}>${statValue}</span>`;
            container.appendChild(statEl);
        }
    });

    // Handle stress separately
    if (characterStats['Stress'] !== undefined) {
        const stressFill = document.getElementById('stress-fill');
        const stressPercent = Math.min(100, Math.max(0, characterStats['Stress']));
        stressFill.style.width = `${stressPercent}%`;
        stressFill.textContent = `${characterStats['Stress']}%`;
        stressFill.title = `Stress: ${characterStats['Stress']}%`;
    }
}

function renderRecurringTasks() {
    const container = document.getElementById('recurring-tasks-list');
    container.innerHTML = '';
    if (!recurringTasks || recurringTasks.length === 0) {
        container.innerHTML = '<li>No recurring habits set.</li>'; return;
    }
    recurringTasks.forEach(rt => {
        const el = document.createElement('li');
        el.className = `task-item ${rt.is_negative_habit ? 'negative-habit' : ''} ${!rt.is_active ? 'task-completed' : ''}`; // task-completed class dims it
        let attributeText = rt.attribute_name ? `[${rt.attribute_name}]` : '';
        el.innerHTML = `
            <div>
                ${rt.description} ${attributeText}
                <small>
                    (XP: ${rt.xp_value}, Stress: ${rt.stress_effect > 0 ? '+' : ''}${rt.stress_effect})
                    ${rt.last_added_date ? `<br>Last auto-added: ${rt.last_added_date}` : ''}
                </small>
            </div>
            <div class="task-actions">
                <button onclick="toggleRecurringActive(${rt.recurring_task_id})" class="${rt.is_active ? 'btn-warning' : 'btn-success'} btn-small">
                    ${rt.is_active ? '⏸ Pause' : '▶ Resume'}
                </button>
                <button onclick="deleteRecurringTask(${rt.recurring_task_id})" class="btn-danger btn-small">
                    🗑 Delete
                </button>
            </div>
        `;
        container.appendChild(el);
    });
}

function renderQuests() {
    const container = document.getElementById('quests-container');
    container.innerHTML = '';
    const activeQuests = quests.filter(q => q.status === 'Active');
    const completedQuests = quests.filter(q => q.status === 'Completed').sort((a,b) => new Date(b.completed_date) - new Date(a.completed_date)).slice(0,3);

    if (activeQuests.length === 0 && completedQuests.length === 0) {
        container.innerHTML = '<p>No quests here. Time for an adventure!</p>'; return;
    }

    if (activeQuests.length > 0) {
        const activeHeader = document.createElement('h4'); activeHeader.className = 'section-subheader'; activeHeader.textContent = 'Active Quests'; container.appendChild(activeHeader);
        activeQuests.forEach(q => container.appendChild(createQuestCard(q)));
    }
    if (completedQuests.length > 0) {
        const completedHeader = document.createElement('h4'); completedHeader.className = 'section-subheader'; completedHeader.textContent = 'Recently Completed'; container.appendChild(completedHeader);
        completedQuests.forEach(q => container.appendChild(createQuestCard(q)));
    }
}

function createQuestCard(quest) {
    const card = document.createElement('div');
    card.className = `quest-card quest-difficulty-${quest.difficulty.toLowerCase()} ${quest.status !== 'Active' ? 'quest-completed-card' : ''}`;
    
    let dueStatus = '';
    if (quest.status === 'Active' && quest.due_date) {
        const dueDate = new Date(quest.due_date + "T23:59:59"); // Consider end of day for due date
        const today = new Date();
        const diffTime = dueDate - today;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        if (diffDays < 0) dueStatus = `<span style="color: var(--negative-color);">Overdue!</span>`;
        else if (diffDays === 0) dueStatus = `<span style="color: var(--neutral-color);">Due Today!</span>`;
        else dueStatus = `Due in ${diffDays} day(s)`;
    } else if (quest.status === 'Completed') {
        dueStatus = `Completed: ${quest.completed_date}`;
    } else {
        dueStatus = 'No due date';
    }

    card.innerHTML = `
        <div class="quest-title-line">
            <span class="quest-title">${quest.title}</span>
            <span class="quest-difficulty-badge quest-difficulty-${quest.difficulty}">${quest.difficulty}</span>
        </div>
        <p class="quest-description">${quest.description || 'No description provided.'}</p>
        <div class="quest-details">
            <span class="quest-attribute-tag">Focus: ${quest.attribute_focus || 'General'}</span>
            <span class="quest-xp-tag">XP: ${quest.xp_reward}</span>
            <span>${dueStatus}</span>
        </div>
        ${quest.status === 'Active' ? `<button onclick="completeQuest(${quest.id})" class="btn-success btn-small">⚔ Complete Quest</button>` : ''}
    `;
    return card;
}

function renderMilestones() {
    const container = document.getElementById('milestones-container');
    container.innerHTML = '';
    if (!milestones.data || milestones.data.length === 0) {
        container.innerHTML = '<p>No achievements yet. Keep up the great work!</p>'; return;
    }
    milestones.data.forEach(m => {
        const el = document.createElement('div');
        el.className = 'milestone';
        el.innerHTML = `
            <button class="btn-danger btn-small" style="float:right; opacity:0.7;" onclick="deleteMilestone(${m.id})" title="Delete Achievement">✕</button>
            <div class="milestone-title">${m.title}</div>
            <p class="milestone-description">${m.description}</p>
            <div class="milestone-date">
                <span>${m.date} (${m.type})</span>
                ${m.attribute ? `<span>— ${m.attribute}</span>` : ''}
            </div>
        `;
        container.appendChild(el);
    });
}

function renderDailyNarrative(narrativeContent, dateForNarrative = currentSelectedDate) {
    const container = document.getElementById('daily-narrative').querySelector('.narrative-content');
    container.innerHTML = narrativeContent ? narrativeContent.replace(/\n/g, '<br>') : 'No narrative available for this day. Perhaps an adventure awaits?';
}

function renderNarrativeHistory() {
    const container = document.getElementById('narrative-history-container');
    container.innerHTML = '';
    if (!narratives.data || narratives.data.length === 0) {
        container.innerHTML = '<p>No past adventures recorded in this chapter.</p>'; return;
    }
    narratives.data.forEach(n => {
        const el = document.createElement('div');
        el.className = 'narrative-item'; // Use .narrative-item for list items
        el.innerHTML = `
            <div class="narrative-date"><strong>${n.date}</strong></div>
            <div class="narrative-content">${n.narrative.replace(/\n/g, '<br>')}</div>
        `;
        container.appendChild(el);
    });
}

function renderHeatmap(year, month, data) { // month is 1-indexed
    const container = document.getElementById('calendar-heatmap-display');
    container.innerHTML = '';
    if (!data) { container.innerHTML = '<p>Loading heatmap data...</p>'; return; }

    const activityMap = new Map(data.map(item => [item.date, { count: item.count, xp: item.xp }]));
    const table = document.createElement('table');
    table.className = 'calendar-table';
    const headerRow = table.insertRow();
    ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].forEach(dayName => {
        const th = document.createElement('th'); th.textContent = dayName; headerRow.appendChild(th);
    });

    const firstDayOfMonth = new Date(year, month - 1, 1).getDay();
    const daysInMonth = new Date(year, month, 0).getDate();

    let currentDay = 1;
    for (let i = 0; i < 6; i++) {
        const weekRow = table.insertRow();
        for (let j = 0; j < 7; j++) {
            const dayCell = weekRow.insertCell();
            if (i === 0 && j < firstDayOfMonth) {
                dayCell.className = 'calendar-empty-day';
            } else if (currentDay <= daysInMonth) {
                dayCell.className = 'calendar-day';
                const dayNumberDiv = document.createElement('div');
                dayNumberDiv.className = 'calendar-day-number';
                dayNumberDiv.textContent = currentDay;
                dayCell.appendChild(dayNumberDiv);

                const dateStr = `${year}-${String(month).padStart(2,'0')}-${String(currentDay).padStart(2,'0')}`;
                const activity = activityMap.get(dateStr);
                let intensityLevel = 0;
                if (activity) {
                    const dataDiv = document.createElement('div');
                    dataDiv.className = 'calendar-day-data';
                    dataDiv.innerHTML = `Tasks: ${activity.count}<br>XP: ${activity.xp}`;
                    dayCell.appendChild(dataDiv);
                    
                    if (activity.xp > 0) intensityLevel = 1;
                    if (activity.xp >= 50) intensityLevel = 2;
                    if (activity.xp >= 100) intensityLevel = 3;
                    if (activity.xp >= 200) intensityLevel = 4;
                    
                    dayCell.addEventListener('mouseenter', (e) => showTooltip(e, `${dateStr}: ${activity.count} tasks, ${activity.xp} XP`));
                    dayCell.addEventListener('mouseleave', hideTooltip);
                }
                dayCell.classList.add(`day-level-${intensityLevel}`);
                currentDay++;
            } else {
                dayCell.className = 'calendar-empty-day';
            }
        }
        if (currentDay > daysInMonth) break;
    }
    container.appendChild(table);
}

function updateHeatmapControlsLabel() {
    const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    document.getElementById('current-heatmap-month-year').textContent = `${monthNames[heatmapCurrentDate.getMonth()]} ${heatmapCurrentDate.getFullYear()}`;
}

function navigateHeatmapMonth(direction) {
    heatmapCurrentDate.setMonth(heatmapCurrentDate.getMonth() + direction);
    updateHeatmapControlsLabel();
    fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1); // Month is 1-indexed for API
}

function renderAttributeHistory(data) {
    const ctx = document.getElementById('attribute-history-chart')?.getContext('2d');
    if (!ctx || !data || !data.dates || !data.attributes) {
        console.warn("Attribute history chart canvas or data not found.");
        return;
    }

    const datasets = [];
    const defaultColors = ['#e63946', '#fca311', '#2ec4b6', '#003049', '#a7c957', '#ffbe0b', '#540b0e', '#0ead69'];
    let colorIndex = 0;

    for (const [attrName, levels] of Object.entries(data.attributes)) {
        if (levels.some(l => l > 0)) { // Only plot if there's some progress
            datasets.push({
                label: attrName,
                data: levels,
                borderColor: defaultColors[colorIndex % defaultColors.length],
                backgroundColor: defaultColors[colorIndex % defaultColors.length] + '33', // Add alpha for fill
                tension: 0.2, // Smoother lines
                fill: false, // No fill under line
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 5
            });
            colorIndex++;
        }
    }

    if (attributeHistoryChart) {
        attributeHistoryChart.data.labels = data.dates;
        attributeHistoryChart.data.datasets = datasets;
        attributeHistoryChart.update();
    } else if (typeof Chart !== 'undefined') {
        attributeHistoryChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.dates,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { 
                    y: { 
                        beginAtZero: true, 
                        title: { display: true, text: 'Level' },
                        ticks: { stepSize: 1 } // Integer levels
                    },
                    x: { 
                        title: {display: true, text: 'Date'}, 
                        ticks: { autoSkip: true, maxTicksLimit: 10 } 
                    } 
                },
                plugins: { 
                    legend: { position: 'bottom' }, 
                    title: { display: true, text: 'Attribute Progress (Last 30 Days)', font: {size: 16, family: "'MedievalSharp', cursive"} } 
                },
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
            }
        });
    }
}

// --- Utility Functions ---
function populateAttributeDropdowns() {
    const attributeSelects = ['task-attribute', 'recurring-task-attribute', 'quest-attribute'];
    attributeSelects.forEach(selectId => {
        const selectElement = document.getElementById(selectId);
        if (!selectElement) return;
        
        const firstOptionValue = selectElement.options[0]?.value; // Preserve "No/Any Attribute"
        selectElement.innerHTML = ''; // Clear existing
        
        if (firstOptionValue !== undefined) { // Add back the first option
            const firstOpt = document.createElement('option');
            firstOpt.value = firstOptionValue;
            firstOpt.textContent = selectId === 'quest-attribute' ? 'Any Attribute' : 'No Attribute';
            selectElement.appendChild(firstOpt);
        }

        attributes.forEach(attr => {
            const option = document.createElement('option');
            option.value = attr.name;
            option.textContent = `${attr.name} (Lvl ${attr.level})`;
            selectElement.appendChild(option);
        });
    });
}

function renderPagination(containerId, infoContainerId, pageDataObject, fetchCallback) {
    const container = document.getElementById(containerId);
    const infoContainer = document.getElementById(infoContainerId);
    container.innerHTML = '';
    if (infoContainer) infoContainer.innerHTML = '';

    if (!pageDataObject || pageDataObject.totalPages <= 1) return;

    if (pageDataObject.page > 1) {
        const prevBtn = document.createElement('button');
        prevBtn.innerHTML = '« Prev';
        prevBtn.className = 'btn-secondary btn-small';
        prevBtn.onclick = () => fetchCallback(pageDataObject.page - 1);
        container.appendChild(prevBtn);
    }
    
    // Simple page number display (could be expanded)
    const pageNumSpan = document.createElement('span');
    pageNumSpan.textContent = ` Page ${pageDataObject.page} of ${pageDataObject.totalPages} `;
    pageNumSpan.style.margin = "0 10px";
    container.appendChild(pageNumSpan);

    if (pageDataObject.page < pageDataObject.totalPages) {
        const nextBtn = document.createElement('button');
        nextBtn.innerHTML = 'Next »';
        nextBtn.className = 'btn-secondary btn-small';
        nextBtn.onclick = () => fetchCallback(pageDataObject.page + 1);
        container.appendChild(nextBtn);
    }
    if (infoContainer) infoContainer.textContent = `Showing page ${pageDataObject.page} of ${pageDataObject.totalPages}. Total items: ${pageDataObject.total || 'N/A'}`;
}

const tooltipElement = document.getElementById('tooltip');
function showTooltip(event, text) {
    if (!tooltipElement) return;
    tooltipElement.innerHTML = text; // Use innerHTML if text contains HTML, else textContent
    tooltipElement.style.display = 'block';
    // Position tooltip carefully to avoid going off-screen
    let x = event.pageX + 15;
    let y = event.pageY + 15;
    if (x + tooltipElement.offsetWidth > window.innerWidth) {
        x = event.pageX - tooltipElement.offsetWidth - 15;
    }
    if (y + tooltipElement.offsetHeight > window.innerHeight) {
        y = event.pageY - tooltipElement.offsetHeight - 15;
    }
    tooltipElement.style.left = x + 'px';
    tooltipElement.style.top = y + 'px';
}
function hideTooltip() {
    if (!tooltipElement) return;
    tooltipElement.style.display = 'none';
}
