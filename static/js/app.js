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
let heatmapCurrentDate = new Date();

// --- DOM Ready Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    checkAPIKey();
    document.getElementById('selected-date').value = currentSelectedDate;
    initializePageData();
    setupEventListeners();
});

function checkAPIKey() {
    const apiKey = localStorage.getItem('openai_api_key');
    if (!apiKey) document.getElementById('apiKeyModal').style.display = 'block';
    else enableAIFeatures();
}

function enableAIFeatures() {
    document.querySelectorAll('[id*="generate"], [id*="enhance"]').forEach(btn => {
        btn.disabled = false;
        btn.textContent = btn.textContent.replace(' (AI)', '');
    });
}

function saveApiKey() {
    const apiKey = document.getElementById('apiKeyInput').value;
    if (!apiKey) return alert('Please enter an API key');
    apiCall('/api/test_api_key', 'POST', {api_key: apiKey}).then(data => {
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
    document.querySelectorAll('[id*="generate"], [id*="enhance"]').forEach(btn => {
        btn.disabled = true;
    });
}

async function initializePageData() {
    console.log("Initializing all page data...");
    await fetchAndRenderAttributes();
    const fetches = [
        fetchAndRenderTasks(currentSelectedDate),
        fetchAndRenderStats(),
        fetchAndRenderRecurringTasks(),
        fetchAndRenderQuests(),
        fetchAndRenderMilestones(milestones.page),
        fetchAndRenderDailyNarrative(currentSelectedDate),
        fetchAndRenderNarrativeHistory(narratives.page),
        fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1),
        fetchAndRenderAttributeHistory(),
        fetchAndRenderHabitProgressor()
    ];
    await Promise.all(fetches);
    updateHeatmapControlsLabel();
}

// --- Event Listener Setup ---
function setupEventListeners() {
    document.getElementById('selected-date').addEventListener('change', handleDateChange);
    document.getElementById('add-task-btn').addEventListener('click', () => toggleForm('add-task-form-container'));
    document.getElementById('add-task-form').addEventListener('submit', handleAddTask);
    document.getElementById('task-stress').addEventListener('input', e => { document.getElementById('task-stress-value-display').textContent = e.target.value; });
    setupRadioGroup('task-type-radio', 'task-difficulty-group', 'task-stress', 'task-stress-value-display', 'task-numeric-inputs');
    document.getElementById('reset-day-btn').addEventListener('click', handleResetDay);
    document.getElementById('add-recurring-task-btn').addEventListener('click', () => toggleForm('add-recurring-task-form-container'));
    document.getElementById('add-recurring-task-form').addEventListener('submit', handleAddRecurringTask);
    document.getElementById('recurring-task-stress').addEventListener('input', e => { document.getElementById('recurring-task-stress-value-display').textContent = e.target.value; });
    setupRadioGroup('recurring-task-type-radio', 'recurring-task-difficulty-group', 'recurring-task-stress', 'recurring-task-stress-value-display', 'recurring-task-numeric-inputs');
    document.getElementById('add-quest-btn').addEventListener('click', () => toggleForm('add-quest-form-container'));
    document.getElementById('add-quest-form').addEventListener('submit', handleAddQuest);
    document.getElementById('generate-quest-btn').addEventListener('click', handleGenerateQuest);
    document.getElementById('enhance-quest-desc-btn').addEventListener('click', enhanceQuestDescription);
    document.getElementById('refresh-narrative-btn').addEventListener('click', () => fetchAndRenderDailyNarrative(currentSelectedDate, true));
    document.getElementById('prev-month-heatmap').addEventListener('click', () => navigateHeatmapMonth(-1));
    document.getElementById('next-month-heatmap').addEventListener('click', () => navigateHeatmapMonth(1));
    document.getElementById('habit-progress-select').addEventListener('change', handleHabitProgressSelection);
    document.getElementById('edit-quest-form').addEventListener('submit', handleUpdateQuest); // NEW
}

function toggleForm(formContainerId) {
    const container = document.getElementById(formContainerId);
    container.style.display = container.style.display === 'none' ? 'block' : 'none';
}

function setupRadioGroup(groupId, difficultyGroupId, stressSliderId, stressValueDisplayId, numericInputsId) {
    const group = document.getElementById(groupId);
    if (!group) return;

    const options = group.querySelectorAll('.radio-option');
    const difficultyGroup = document.getElementById(difficultyGroupId);
    const numericInputs = document.getElementById(numericInputsId);

    options.forEach(option => {
        option.addEventListener('click', () => {
            options.forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');
            
            const isNegative = option.dataset.value === 'negative';
            
            if (difficultyGroup) difficultyGroup.style.display = isNegative ? 'none' : 'block';
            if (numericInputs) numericInputs.style.display = isNegative ? 'none' : 'flex';

            const stressSlider = document.getElementById(stressSliderId);
            const stressValueDisplay = document.getElementById(stressValueDisplayId);

            if (stressSlider && stressValueDisplay) {
                let currentStress = parseInt(stressSlider.value);
                stressSlider.value = isNegative ? Math.abs(currentStress) || 3 : -(Math.abs(currentStress) || 3);
                stressValueDisplay.textContent = stressSlider.value;
            }
        });
    });
    const selectedOption = group.querySelector('.radio-option.selected') || options[0];
    if (selectedOption) selectedOption.click();
}

// --- Enhanced Features ---
async function enhanceQuestDescription() {
    const apiKey = localStorage.getItem('openai_api_key');
    if (!apiKey) return document.getElementById('apiKeyModal').style.display = 'block';
    
    const descriptionField = document.getElementById('quest-description');
    const originalDescription = descriptionField.value.trim();
    if (!originalDescription) return alert('Please enter a description first');
    
    const enhanceBtn = document.getElementById('enhance-quest-desc-btn');
    enhanceBtn.disabled = true;
    enhanceBtn.textContent = 'Enhancing...';
    
    try {
        const response = await apiCall('/api/enhance_quest_description', 'POST', { api_key: apiKey, description: originalDescription });
        if (response && response.enhanced_description) {
            descriptionField.value = response.enhanced_description;
        }
    } catch (error) { console.error('Error enhancing description:', error); }
    
    enhanceBtn.disabled = false;
    enhanceBtn.textContent = '✨ Enhance (AI)';
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
    const isNegative = form.querySelector('#task-type-radio .selected').dataset.value === 'negative';
    const payload = {
        description: form.querySelector('#task-description').value,
        attribute: form.querySelector('#task-attribute').value,
        difficulty: form.querySelector('#task-difficulty').value,
        stress_effect: parseInt(form.querySelector('#task-stress').value),
        is_negative_habit: isNegative,
        date: currentSelectedDate,
        numeric_value: isNegative ? null : form.querySelector('#task-numeric-value').value || null,
        numeric_unit: isNegative ? null : form.querySelector('#task-numeric-unit').value || null
    };

    const result = await apiCall('/api/add_task', 'POST', payload);
    if (result && result.success) {
        form.reset();
        setupRadioGroup('task-type-radio', 'task-difficulty-group', 'task-stress', 'task-stress-value-display', 'task-numeric-inputs');
        toggleForm('add-task-form-container');
        await fetchAndRenderTasks(currentSelectedDate);
        if (!isNegative && payload.attribute) await fetchAndRenderAttributes();
        await Promise.all([fetchAndRenderStats(), fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1), fetchAndRenderHabitProgressor()]);
    }
}

async function handleResetDay() {
    if (!confirm(`Are you sure you want to reset all data for ${currentSelectedDate}? This action cannot be undone.`)) return;
    const result = await apiCall('/api/reset_day', 'POST', { date: currentSelectedDate });
    if (result && result.success) {
        alert(`Day ${result.date} has been reset. Tasks deleted: ${result.tasks_deleted}.`);
        await initializePageData();
    }
}

async function handleAddRecurringTask(event) {
    event.preventDefault();
    const form = event.target;
    const isNegative = form.querySelector('#recurring-task-type-radio .selected').dataset.value === 'negative';
    const payload = {
        description: form.querySelector('#recurring-task-description').value,
        attribute: form.querySelector('#recurring-task-attribute').value,
        difficulty: form.querySelector('#recurring-task-difficulty').value,
        stress_effect: parseInt(form.querySelector('#recurring-task-stress').value),
        is_negative_habit: isNegative,
        numeric_value: isNegative ? null : form.querySelector('#recurring-task-numeric-value').value || null,
        numeric_unit: isNegative ? null : form.querySelector('#recurring-task-numeric-unit').value || null
    };
    const result = await apiCall('/api/recurring_tasks', 'POST', payload);
    if (result && result.success) {
        form.reset();
        setupRadioGroup('recurring-task-type-radio', 'recurring-task-difficulty-group', 'recurring-task-stress', 'recurring-task-stress-value-display', 'recurring-task-numeric-inputs');
        toggleForm('add-recurring-task-form-container');
        await fetchAndRenderRecurringTasks();
        await fetchAndRenderTasks(currentSelectedDate);
        await fetchAndRenderHabitProgressor();
    }
}

async function handleAddQuest(event) {
    event.preventDefault();
    const form = event.target;
    const diffToXp = {"Easy": 50, "Medium": 100, "Hard": 175, "Epic": 250};
    const payload = {
        title: form.querySelector('#quest-title').value,
        description: form.querySelector('#quest-description').value,
        difficulty: form.querySelector('#quest-difficulty').value,
        attribute_focus: form.querySelector('#quest-attribute').value,
        due_date: form.querySelector('#quest-due-date').value || null,
        xp_reward: diffToXp[form.querySelector('#quest-difficulty').value] || 100
    };
    const result = await apiCall('/api/quests', 'POST', payload);
    if (result && result.success) {
        form.reset();
        toggleForm('add-quest-form-container');
        await fetchAndRenderQuests();
        await fetchAndRenderStats();
    }
}

async function handleGenerateQuest() {
    const apiKey = localStorage.getItem('openai_api_key');
    if (!apiKey) return document.getElementById('apiKeyModal').style.display = 'block';
    
    const form = document.getElementById('add-quest-form');
    const questData = await apiCall('/api/generate_quest', 'POST', { 
        attribute_focus: form.querySelector('#quest-attribute').value, 
        difficulty: form.querySelector('#quest-difficulty').value,
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

async function handleHabitProgressSelection(event) {
    const selectedHabit = event.target.value;
    const displayEl = document.getElementById('habit-progress-display');
    if (!selectedHabit) return displayEl.style.display = 'none';
    const progressData = await apiCall(`/api/habit_progress?description=${encodeURIComponent(selectedHabit)}`);
    if (progressData) {
        renderHabitProgress(progressData);
        displayEl.style.display = 'block';
    }
}

async function handleUpdateQuest(event) {
    event.preventDefault();
    const form = event.target;
    const questId = form.querySelector('#edit-quest-id').value;
    const payload = {
        title: form.querySelector('#edit-quest-title').value,
        description: form.querySelector('#edit-quest-description').value,
        difficulty: form.querySelector('#edit-quest-difficulty').value,
        attribute_focus: form.querySelector('#edit-quest-attribute').value,
        due_date: form.querySelector('#edit-quest-due-date').value || null
    };
    const result = await apiCall(`/api/quests/${questId}`, 'PUT', payload);
    if (result && result.success) {
        document.getElementById('editQuestModal').style.display = 'none';
        await fetchAndRenderQuests();
    }
}

// --- Action Functions ---
async function completeTask(taskId, isNumeric = false, unit = '', forcedValue = null) {
    const taskElement = document.querySelector(`button[onclick*="completeTask(${taskId})"]`)?.closest('.task-item');
    if (taskElement) taskElement.style.opacity = '0.5';

    let payload = { task_id: taskId };

    if (forcedValue !== null) {
        payload.logged_numeric_value = forcedValue;
    } else if (isNumeric) {
        const loggedValue = prompt(`How many ${unit} did you complete? (Enter 0 if none)`);
        if (loggedValue === null || isNaN(parseFloat(loggedValue))) {
            if (taskElement) taskElement.style.opacity = '1';
            if (loggedValue !== null) alert('Invalid number entered.');
            return;
        }
        payload.logged_numeric_value = parseFloat(loggedValue);
    }

    const result = await apiCall('/api/complete_task', 'POST', payload);
    if (result && result.success) {
        await fetchAndRenderTasks(currentSelectedDate);
        await Promise.all([fetchAndRenderAttributes(), fetchAndRenderStats(), fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1)]);
        if (isNumeric) await fetchAndRenderHabitProgressor(true);
        if (Math.random() < 0.2) await fetchAndRenderMilestones(milestones.page);
    } else {
        if (taskElement) taskElement.style.opacity = '1';
    }
}

async function skipTask(taskId) {
    if (!confirm('Mark this task as skipped?')) return;
    const result = await apiCall('/api/skip_task', 'POST', { task_id: taskId });
    if (result && result.success) {
        await fetchAndRenderTasks(currentSelectedDate);
        await fetchAndRenderStats();
    }
}

async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) return;
    const result = await apiCall('/api/delete_task', 'POST', { task_id: taskId });
    if (result && result.success) {
        await fetchAndRenderTasks(currentSelectedDate);
        await Promise.all([fetchAndRenderAttributes(), fetchAndRenderStats(), fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1), fetchAndRenderHabitProgressor()]);
    }
}

async function deleteRecurringTask(rtId) {
    if (!confirm('Delete this recurring habit permanently?')) return;
    const result = await apiCall(`/api/recurring_tasks/${rtId}`, 'DELETE');
    if (result && result.success) {
        await fetchAndRenderRecurringTasks();
        await fetchAndRenderHabitProgressor();
    }
}

async function toggleRecurringActive(rtId) {
    const result = await apiCall(`/api/recurring_tasks/${rtId}/toggle_active`, 'POST');
    if (result && result.success) {
        await fetchAndRenderRecurringTasks();
        await fetchAndRenderTasks(currentSelectedDate);
    }
}

async function completeQuest(questId) {
    if (!confirm('Mark this quest as completed?')) return;
    const result = await apiCall('/api/complete_quest', 'POST', { quest_id: questId });
    if (result && result.success) {
        await Promise.all([fetchAndRenderQuests(), fetchAndRenderAttributes(), fetchAndRenderStats(), fetchAndRenderMilestones(milestones.page), fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1)]);
    }
}

async function deleteMilestone(milestoneId) {
    if (!confirm('Are you sure you want to delete this achievement?')) return;
    const result = await apiCall('/api/delete_milestone', 'POST', { milestone_id: milestoneId });
    if (result && result.success) await fetchAndRenderMilestones(milestones.page);
}

// --- NEW QUEST STEP FUNCTIONS ---
function toggleQuest(questId) {
    const questElement = document.getElementById(`quest-accordion-${questId}`);
    questElement.classList.toggle('expanded');
}

function openEditQuestModal(questId) {
    const quest = quests.find(q => q.id === questId);
    if (!quest) return;
    const form = document.getElementById('edit-quest-form');
    form.querySelector('#edit-quest-id').value = quest.id;
    form.querySelector('#edit-quest-title').value = quest.title;
    form.querySelector('#edit-quest-description').value = quest.description;
    form.querySelector('#edit-quest-difficulty').value = quest.difficulty;
    form.querySelector('#edit-quest-attribute').value = quest.attribute_focus || "";
    form.querySelector('#edit-quest-due-date').value = quest.due_date || "";
    document.getElementById('editQuestModal').style.display = 'block';
}

async function addQuestStep(questId) {
    const input = document.getElementById(`add-step-input-${questId}`);
    const description = input.value.trim();
    if (!description) return;
    const result = await apiCall(`/api/quests/${questId}/add_step`, 'POST', { description });
    if (result && result.success) {
        input.value = '';
        await fetchAndRenderQuests();
    }
}

async function toggleQuestStep(stepId) {
    const result = await apiCall(`/api/quest_steps/${stepId}/toggle`, 'POST');
    if (result && result.success) await fetchAndRenderQuests();
}

async function deleteQuestStep(stepId) {
    if (!confirm('Delete this quest step?')) return;
    const result = await apiCall(`/api/quest_steps/${stepId}`, 'DELETE');
    if (result && result.success) await fetchAndRenderQuests();
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
        const responseData = await response.json();
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

// --- Fetch and Render Sections ---
async function fetchAndRenderAttributes() { attributes = await apiCall('/api/attributes') || []; renderAttributes(); populateAttributeDropdowns(); }
async function fetchAndRenderTasks(date) { tasks = await apiCall(`/api/tasks?date=${date}`) || []; renderTasks(); }
async function fetchAndRenderStats() { characterStats = await apiCall('/api/stats') || {}; renderCharacterStats(); }
async function fetchAndRenderRecurringTasks() { recurringTasks = await apiCall('/api/recurring_tasks') || []; renderRecurringTasks(); }
async function fetchAndRenderQuests() { quests = await apiCall('/api/quests') || []; renderQuests(); }
async function fetchAndRenderMilestones(page) {
    const data = await apiCall(`/api/milestones?page=${page}&per_page=${milestones.perPage}`);
    if (data) { Object.assign(milestones, { data: data.milestones, page: data.current_page, totalPages: data.pages }); renderMilestones(); renderPagination('milestones-pagination', 'milestones-pagination-info', milestones, fetchAndRenderMilestones); }
}
async function fetchAndRenderDailyNarrative(date, forceRegenerate = false) {
    const apiKey = localStorage.getItem('openai_api_key');
    const data = forceRegenerate && apiKey ? await apiCall('/api/generate_narrative', 'POST', { date, api_key: apiKey }) : await apiCall(`/api/narrative?date=${date}`);
    if (data) { renderDailyNarrative(data.narrative); if (forceRegenerate) await fetchAndRenderNarrativeHistory(1); }
}
async function fetchAndRenderNarrativeHistory(page) {
    const data = await apiCall(`/api/narratives?page=${page}&per_page=${narratives.perPage}`);
    if (data) { Object.assign(narratives, { data: data.narratives, page: data.current_page, totalPages: data.pages }); renderNarrativeHistory(); renderPagination('narratives-pagination', 'narratives-pagination-info', narratives, fetchAndRenderNarrativeHistory); }
}
async function fetchAndRenderHeatmap(year, month) { const data = await apiCall(`/api/heatmap?year=${year}&month=${month}`); if (data) renderHeatmap(year, month, data); }
async function fetchAndRenderAttributeHistory() { const data = await apiCall('/api/attribute_history?days=30'); if (data) renderAttributeHistory(data); }
async function fetchAndRenderHabitProgressor(refreshCurrent = false) {
    const habitList = await apiCall('/api/get_numeric_habits');
    const selectEl = document.getElementById('habit-progress-select');
    if (habitList) {
        populateHabitProgressDropdown(habitList, selectEl.value);
        if (refreshCurrent && selectEl.value) {
            const progressData = await apiCall(`/api/habit_progress?description=${encodeURIComponent(selectEl.value)}`);
            if (progressData) renderHabitProgress(progressData);
        }
    }
}

// --- DOM Rendering Functions ---
function renderAttributes() {
    const container = document.getElementById('attributes-container'); container.innerHTML = '';
    if (!attributes || attributes.length === 0) return container.innerHTML = '<p>No attributes data.</p>';
    attributes.forEach(attr => {
        const attrEl = document.createElement('div'); attrEl.className = 'attribute-progress';
        attrEl.innerHTML = `<div><span>${attr.name}</span><span class="attribute-level">Lvl ${attr.level}</span></div><div class="progress-bar"><div class="progress-bar-fill" style="width: ${attr.progress_percent}%" title="${attr.xp_progress}/${attr.xp_needed} XP">${Math.round(attr.progress_percent)}%</div></div><small>Total XP: ${attr.total_xp}</small>`;
        if (attr.subskills) attr.subskills.filter(sub => sub.total_xp > 0).forEach(sub => {
            const subEl = document.createElement('div'); subEl.className = 'subskill-progress';
            subEl.innerHTML = `<div><span>${sub.name}</span><span class="subskill-level">Lvl ${sub.level}</span></div><div class="progress-bar"><div class="progress-bar-fill" style="width: ${sub.progress_percent}%" title="${sub.xp_progress}/${sub.xp_needed} XP">${Math.round(sub.progress_percent)}%</div></div>`;
            attrEl.appendChild(subEl);
        });
        container.appendChild(attrEl);
    });
}
function renderTasks() {
    const container = document.getElementById('task-list'); container.innerHTML = '';
    if (!tasks || tasks.length === 0) return container.innerHTML = '<li>No tasks for this day.</li>';
    tasks.forEach(task => {
        const taskEl = document.createElement('li');
        let taskClasses = `task-item ${task.is_negative_habit ? 'negative-habit' : ''} ${task.completed ? 'task-completed' : ''} ${task.skipped ? 'task-skipped' : ''}`;
        taskEl.className = taskClasses.trim();
        
        let attributeText = task.attribute ? `[${task.attribute}${task.subskill ? ` → ${task.subskill}` : ''}]` : '';
        let xpText = task.is_negative_habit ? `(Avoid: ${task.xp || 25} XP)` : `(${task.xp} XP)`;
        let numericText = '';
        if (task.numeric_unit) {
            if (task.completed && task.logged_numeric_value !== null) {
                let goalText = task.numeric_value !== null ? `(Goal: ${task.numeric_value} ${task.numeric_unit})` : '';
                numericText = `<span class="completion-status">Logged: ${task.logged_numeric_value} ${task.numeric_unit} ${goalText}</span>`;
            } else numericText = `(Goal: ${task.numeric_value || 'Any'} ${task.numeric_unit})`;
        }
        
        let actionButtons = '';
        if (task.completed) actionButtons = `<span class="completion-status">✓ Logged!</span>`;
        else if (task.skipped) actionButtons = '<span class="completion-status">⏭ Skipped</span>';
        else if (task.is_negative_habit) {
            actionButtons = task.numeric_unit && task.numeric_unit !== 'occurrence'
                ? `<button onclick="completeTask(${task.id}, true, '${task.numeric_unit}')" class="btn-warning btn-small">📝 Log</button>`
                : `<div class="task-actions negative-habit-actions"><button onclick="completeTask(${task.id}, true, '', 1)" class="btn-danger btn-small">Yes</button><button onclick="completeTask(${task.id}, true, '', 0)" class="btn-success btn-small">No</button></div>`;
        } else {
            actionButtons = `<button onclick="completeTask(${task.id}, ${!!task.numeric_unit}, '${task.numeric_unit}')" class="btn-success btn-small">✓ Complete</button><button onclick="skipTask(${task.id})" class="btn-warning btn-small">⏭ Skip</button>`;
        }
        
        taskEl.innerHTML = `<div>${task.description} ${attributeText} ${xpText} ${numericText}<small>Stress Penalty: +${Math.abs(task.stress_effect)}</small></div><div class="task-actions">${actionButtons}<button onclick="deleteTask(${task.id})" class="btn-danger btn-small">🗑</button></div>`;
        container.appendChild(taskEl);
    });
}
function renderCharacterStats() {
    const container = document.getElementById('character-stats'); container.innerHTML = '';
    const levelDisplay = document.getElementById('character-level');
    if (Object.keys(characterStats).length === 0) return container.innerHTML = '<p>Loading stats...</p>';
    const totalXp = characterStats['Total XP'] || 0;
    levelDisplay.textContent = `Level ${totalXp <= 0 ? 1 : Math.floor(1 + Math.pow(totalXp / 100, 1/2.2))}`;
    ['Total Tasks Completed', 'Tasks Remaining Today', 'Tasks Skipped Today', 'Negative Habits Done', 'Negative Habits Avoided', 'Total XP', 'Active Quests', 'Completed Quests'].forEach(statName => {
        if (characterStats.hasOwnProperty(statName)) {
            const statEl = document.createElement('div'); statEl.className = 'stat-entry';
            let style = (statName === 'Tasks Remaining Today' && characterStats[statName] > 0) ? ' style="color: var(--negative-color); font-weight: bold;"' : '';
            statEl.innerHTML = `<strong${style}>${statName.replace(/([A-Z])/g, ' $1').trim()}:</strong> <span${style}>${characterStats[statName]}</span>`;
            container.appendChild(statEl);
        }
    });
    if (characterStats['Stress'] !== undefined) {
        const stressFill = document.getElementById('stress-fill');
        stressFill.style.width = `${Math.min(100, Math.max(0, characterStats['Stress']))}%`;
        stressFill.textContent = `${characterStats['Stress']}%`;
    }
}
function renderRecurringTasks() {
    const container = document.getElementById('recurring-tasks-list'); container.innerHTML = '';
    if (!recurringTasks || recurringTasks.length === 0) return container.innerHTML = '<li>No recurring habits set.</li>';
    recurringTasks.forEach(rt => {
        const el = document.createElement('li');
        el.className = `task-item ${rt.is_negative_habit ? 'negative-habit' : ''} ${!rt.is_active ? 'task-completed' : ''}`;
        el.innerHTML = `<div>${rt.description} ${rt.attribute_name ? `[${rt.attribute_name}]` : ''} ${rt.numeric_unit ? `(Goal: ${rt.numeric_value} ${rt.numeric_unit})` : ''}<small>(XP: ${rt.xp_value}, Stress: ${rt.stress_effect})</small></div><div class="task-actions"><button onclick="toggleRecurringActive(${rt.recurring_task_id})" class="${rt.is_active ? 'btn-warning' : 'btn-success'} btn-small">${rt.is_active ? '⏸' : '▶'}</button><button onclick="deleteRecurringTask(${rt.recurring_task_id})" class="btn-danger btn-small">🗑</button></div>`;
        container.appendChild(el);
    });
}
function renderQuests() {
    const container = document.getElementById('quests-container'); container.innerHTML = '';
    const activeQuests = quests.filter(q => q.status === 'Active');
    const completedQuests = quests.filter(q => q.status === 'Completed').sort((a,b) => new Date(b.completed_date) - new Date(a.completed_date)).slice(0,3);
    if (quests.length === 0) return container.innerHTML = '<p>No quests here. Time for an adventure!</p>';
    if (activeQuests.length > 0) { const h = document.createElement('h4'); h.className = 'section-subheader'; h.textContent = 'Active Quests'; container.appendChild(h); activeQuests.forEach(q => container.appendChild(createQuestCard(q))); }
    if (completedQuests.length > 0) { const h = document.createElement('h4'); h.className = 'section-subheader'; h.textContent = 'Recently Completed'; container.appendChild(h); completedQuests.forEach(q => container.appendChild(createQuestCard(q))); }
}
function createQuestCard(quest) {
    const card = document.createElement('div'); card.id = `quest-accordion-${quest.id}`;
    card.className = `quest-accordion ${quest.status !== 'Active' ? 'quest-completed-card' : ''}`;
    let dueStatus = '';
    if (quest.status === 'Active' && quest.due_date) {
        const diffDays = Math.ceil((new Date(quest.due_date + "T23:59:59") - new Date()) / 864e5);
        if (diffDays < 0) dueStatus = `<span style="color: var(--negative-color);">Overdue!</span>`;
        else if (diffDays === 0) dueStatus = `<span style="color: var(--neutral-color);">Due Today!</span>`;
        else dueStatus = `Due in ${diffDays} day(s)`;
    } else if (quest.status === 'Completed') dueStatus = `Completed: ${quest.completed_date}`;

    let stepsHtml = quest.steps.map(step => `
        <li class="quest-step ${step.completed ? 'completed' : ''}">
            <input type="checkbox" id="step-${step.id}" onchange="toggleQuestStep(${step.id})" ${step.completed ? 'checked' : ''}>
            <label for="step-${step.id}">${step.description}</label>
            <button onclick="deleteQuestStep(${step.id})" class="btn-danger btn-small">🗑</button>
        </li>
    `).join('');

    card.innerHTML = `
        <div class="quest-header" onclick="toggleQuest(${quest.id})">
            <div class="quest-header-top">
                <span class="quest-title">${quest.title}</span>
                <div class="quest-header-actions">
                    <span class="quest-difficulty-badge quest-difficulty-${quest.difficulty}">${quest.difficulty}</span>
                    <button onclick="event.stopPropagation(); openEditQuestModal(${quest.id})" class="btn-secondary btn-small">✏️</button>
                </div>
            </div>
            <div class="progress-bar"><div class="progress-bar-fill" style="width: ${quest.progress}%">${Math.round(quest.progress)}%</div></div>
        </div>
        <div class="quest-content">
            <p class="quest-description">${quest.description || 'No description.'}</p>
            <div class="quest-details">
                <span class="quest-attribute-tag">Focus: ${quest.attribute_focus || 'General'}</span>
                <span class="quest-xp-tag">XP: ${quest.xp_reward}</span><span>${dueStatus}</span>
            </div>
            <ul class="quest-checklist">${stepsHtml}</ul>
            <div class="add-step-container">
                <input type="text" id="add-step-input-${quest.id}" placeholder="Add new step...">
                <button onclick="event.stopPropagation(); addQuestStep(${quest.id})" class="btn-success btn-small">+ Add</button>
            </div>
            ${quest.status === 'Active' ? `<button onclick="completeQuest(${quest.id})" class="btn-success btn-small" style="margin-top:15px">⚔ Complete Quest</button>` : ''}
        </div>
    `;
    return card;
}
function renderMilestones() {
    const container = document.getElementById('milestones-container'); container.innerHTML = '';
    if (!milestones.data || milestones.data.length === 0) return container.innerHTML = '<p>No achievements yet.</p>';
    milestones.data.forEach(m => {
        const el = document.createElement('div'); el.className = 'milestone';
        el.innerHTML = `<button class="btn-danger btn-small" style="float:right; opacity:0.7;" onclick="deleteMilestone(${m.id})">✕</button><div class="milestone-title">${m.title}</div><p class="milestone-description">${m.description}</p><div class="milestone-date"><span>${m.date} (${m.type})</span>${m.attribute ? `<span>— ${m.attribute}</span>` : ''}</div>`;
        container.appendChild(el);
    });
}
function renderDailyNarrative(content) { document.getElementById('daily-narrative').querySelector('.narrative-content').innerHTML = content ? content.replace(/\n/g, '<br>') : 'No narrative available.'; }
function renderNarrativeHistory() {
    const container = document.getElementById('narrative-history-container'); container.innerHTML = '';
    if (!narratives.data || narratives.data.length === 0) return container.innerHTML = '<p>No past adventures.</p>';
    narratives.data.forEach(n => {
        const el = document.createElement('div'); el.className = 'narrative-item';
        el.innerHTML = `<div class="narrative-date"><strong>${n.date}</strong></div><div class="narrative-content">${n.narrative.replace(/\n/g, '<br>')}</div>`;
        container.appendChild(el);
    });
}
function renderHeatmap(year, month, data) {
    const container = document.getElementById('calendar-heatmap-display'); container.innerHTML = '';
    if (!data) return container.innerHTML = '<p>Loading heatmap...</p>';
    const activityMap = new Map(data.map(item => [item.date, { count: item.count, xp: item.xp }]));
    const table = document.createElement('table'); table.className = 'calendar-table';
    const headerRow = table.insertRow();
    ["S", "M", "T", "W", "T", "F", "S"].forEach(d => { const th = document.createElement('th'); th.textContent = d; headerRow.appendChild(th); });
    const firstDay = new Date(year, month - 1, 1).getDay();
    const daysInMonth = new Date(year, month, 0).getDate();
    let currentDay = 1;
    for (let i = 0; i < 6 && currentDay <= daysInMonth; i++) {
        const weekRow = table.insertRow();
        for (let j = 0; j < 7; j++) {
            const dayCell = weekRow.insertCell();
            if (i === 0 && j < firstDay || currentDay > daysInMonth) dayCell.className = 'calendar-empty-day';
            else {
                dayCell.className = 'calendar-day';
                const dateStr = `${year}-${String(month).padStart(2,'0')}-${String(currentDay).padStart(2,'0')}`;
                const activity = activityMap.get(dateStr);
                let level = 0;
                if (activity) { if (activity.xp > 0) level = 1; if (activity.xp >= 50) level = 2; if (activity.xp >= 100) level = 3; if (activity.xp >= 200) level = 4; }
                dayCell.innerHTML = `<div class="calendar-day-number">${currentDay}</div>`;
                dayCell.classList.add(`day-level-${level}`);
                currentDay++;
            }
        }
    }
    container.appendChild(table);
}
function renderAttributeHistory(data) {
    const ctx = document.getElementById('attribute-history-chart')?.getContext('2d');
    if (!ctx || !data) return;
    const datasets = Object.entries(data.attributes).map(([name, levels], i) => ({
        label: name, data: levels, tension: 0.2, fill: false, borderWidth: 2,
        borderColor: ['#e63946', '#fca311', '#2ec4b6', '#003049', '#a7c957', '#540b0e'][i % 6]
    }));
    if (attributeHistoryChart) {
        Object.assign(attributeHistoryChart.data, { labels: data.dates, datasets });
        attributeHistoryChart.update();
    } else {
        attributeHistoryChart = new Chart(ctx, { type: 'line', data: { labels: data.dates, datasets }, options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }, plugins: { legend: { position: 'bottom' } } } });
    }
}
function renderHabitProgress(data) {
    const weekContainer = document.getElementById('habit-progress-week');
    const monthContainer = document.getElementById('habit-progress-month');
    const { unit, is_negative } = data;
    const progressHeader = document.querySelector('#habit-progress-display h4');
    if (progressHeader) {
        let label = progressHeader.querySelector('.habit-goal-label');
        if (!label) { label = document.createElement('span'); label.className = 'habit-goal-label'; progressHeader.appendChild(label); }
        label.textContent = is_negative ? '(Goal: Lower is Better)' : '';
    }
    const formatChange = c => c > 0 ? `<span class="progress-change positive">▲ ${c}%</span>` : (c < 0 ? `<span class="progress-change negative">▼ ${Math.abs(c)}%</span>` : `<span class="progress-change neutral">--</span>`);
    const f = (val) => val.toFixed(1);
    weekContainer.innerHTML = `<div class="progress-period"><h5>Last Week</h5><div class="progress-stat">Total: <span class="value">${f(data.week.last_week.total)}</span> ${unit}</div><div class="progress-stat">Avg: <span class="value">${f(data.week.last_week.avg)}</span> ${unit}</div></div><div class="progress-period"><h5>This Week</h5><div class="progress-stat">Total: <span class="value">${f(data.week.this_week.total)}</span> ${unit} ${formatChange(data.week.total_change)}</div><div class="progress-stat">Avg: <span class="value">${f(data.week.this_week.avg)}</span> ${unit} ${formatChange(data.week.avg_change)}</div></div>`;
    monthContainer.innerHTML = `<div class="progress-period"><h5>Last Month</h5><div class="progress-stat">Total: <span class="value">${f(data.month.last_month.total)}</span> ${unit}</div><div class="progress-stat">Avg: <span class="value">${f(data.month.last_month.avg)}</span> ${unit}</div></div><div class="progress-period"><h5>This Month</h5><div class="progress-stat">Total: <span class="value">${f(data.month.this_month.total)}</span> ${unit} ${formatChange(data.month.total_change)}</div><div class="progress-stat">Avg: <span class="value">${f(data.month.this_month.avg)}</span> ${unit} ${formatChange(data.month.avg_change)}</div></div>`;
}

// --- Utility Functions ---
function populateAttributeDropdowns() {
    ['task-attribute', 'recurring-task-attribute', 'quest-attribute', 'edit-quest-attribute'].forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;
        const firstOptText = select.options[0].textContent;
        select.innerHTML = `<option value="">${firstOptText}</option>`;
        attributes.forEach(attr => { const opt = document.createElement('option'); opt.value = attr.name; opt.textContent = `${attr.name} (Lvl ${attr.level})`; select.appendChild(opt); });
    });
}
function populateHabitProgressDropdown(habitList, currentSelection) {
    const select = document.getElementById('habit-progress-select');
    select.innerHTML = '<option value="">-- Select a habit --</option>';
    if (!habitList || habitList.length === 0) return select.options[0].textContent = '-- No numeric habits yet --';
    habitList.forEach(habit => { const opt = document.createElement('option'); opt.value = habit; opt.textContent = habit; if (habit === currentSelection) opt.selected = true; select.appendChild(opt); });
}
function renderPagination(containerId, infoId, pageData, callback) {
    const container = document.getElementById(containerId);
    const info = document.getElementById(infoId);
    container.innerHTML = ''; info.innerHTML = '';
    if (!pageData || pageData.totalPages <= 1) return;
    if (pageData.page > 1) { const btn = document.createElement('button'); btn.innerHTML = '«'; btn.className = 'btn-secondary btn-small'; btn.onclick = () => callback(pageData.page - 1); container.appendChild(btn); }
    const span = document.createElement('span'); span.textContent = ` ${pageData.page} / ${pageData.totalPages} `; container.appendChild(span);
    if (pageData.page < pageData.totalPages) { const btn = document.createElement('button'); btn.innerHTML = '»'; btn.className = 'btn-secondary btn-small'; btn.onclick = () => callback(pageData.page + 1); container.appendChild(btn); }
}
function updateHeatmapControlsLabel() { document.getElementById('current-heatmap-month-year').textContent = heatmapCurrentDate.toLocaleString('default', { month: 'long', year: 'numeric' }); }
function navigateHeatmapMonth(dir) { heatmapCurrentDate.setMonth(heatmapCurrentDate.getMonth() + dir); updateHeatmapControlsLabel(); fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1); }
