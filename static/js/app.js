// --- Global State Variables ---
let currentSelectedDate = new Date().toISOString().split('T')[0];
let attributes = [];
let tasks = [];
let recurringTasks = [];
let characterStats = {};
let quests = [];
let milestones = { data: [], page: 1, totalPages: 1, perPage: 5 };
let narratives = { data: [], page: 1, totalPages: 1, perPage: 3 };
let heatmapCurrentDate = new Date(); // For heatmap navigation
let notes = []; // For notes feature

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
    
    await fetchAndRenderAttributes();
    
    await fetchAndRenderTasks(currentSelectedDate);
    await fetchAndRenderStats();
    await fetchAndRenderRecurringTasks();
    await fetchAndRenderQuests();
    await fetchAndRenderMilestones(milestones.page);
    await fetchAndRenderDailyNarrative(currentSelectedDate);
    await fetchAndRenderNarrativeHistory(narratives.page);
    await fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1);
    await fetchAndRenderHabitProgressor();
    
    // Initialize new features
    await fetchAndRenderCredo();
    await fetchAndRenderNotes();
    await fetchAndRenderDailyChecklist(currentSelectedDate);
    
    updateHeatmapControlsLabel();
}

// --- Event Listener Setup ---
function setupEventListeners() {
    document.getElementById('selected-date').addEventListener('change', handleDateChange);
    document.getElementById('add-task-btn').addEventListener('click', () => toggleForm('add-task-form-container'));
    document.getElementById('add-task-form').addEventListener('submit', handleAddTask);
    document.getElementById('task-stress').addEventListener('input', (e) => { document.getElementById('task-stress-value-display').textContent = e.target.value; });
    setupRadioGroup('task-type-radio', 'task-difficulty-group', 'task-stress', 'task-stress-value-display', 'task-numeric-inputs');
    document.getElementById('reset-day-btn').addEventListener('click', handleResetDay);
    document.getElementById('add-recurring-task-btn').addEventListener('click', () => toggleForm('add-recurring-task-form-container'));
    document.getElementById('add-recurring-task-form').addEventListener('submit', handleAddRecurringTask);
    document.getElementById('recurring-task-stress').addEventListener('input', (e) => { document.getElementById('recurring-task-stress-value-display').textContent = e.target.value; });
    setupRadioGroup('recurring-task-type-radio', 'recurring-task-difficulty-group', 'recurring-task-stress', 'recurring-task-stress-value-display', 'recurring-task-numeric-inputs');
    document.getElementById('add-quest-btn').addEventListener('click', () => toggleForm('add-quest-form-container'));
    document.getElementById('add-quest-form').addEventListener('submit', handleAddQuest);
    document.getElementById('generate-quest-btn').addEventListener('click', handleGenerateQuest);
    document.getElementById('enhance-quest-desc-btn').addEventListener('click', enhanceQuestDescription);
    document.getElementById('refresh-narrative-btn').addEventListener('click', () => fetchAndRenderDailyNarrative(currentSelectedDate, true));
    document.getElementById('prev-month-heatmap').addEventListener('click', () => navigateHeatmapMonth(-1));
    document.getElementById('next-month-heatmap').addEventListener('click', () => navigateHeatmapMonth(1));
    document.getElementById('habit-progress-select').addEventListener('change', handleHabitProgressSelection);

    // Listeners for Edit Quest Modal
    document.getElementById('close-edit-quest-modal-btn').addEventListener('click', closeEditQuestModal);
    document.getElementById('save-quest-changes-btn').addEventListener('click', handleSaveQuestChanges);
    document.getElementById('add-quest-step-form').addEventListener('submit', handleAddQuestStep);
    
    // Listeners for Credo, Notes, and Daily Checklist
    document.getElementById('save-credo-btn').addEventListener('click', handleSaveCredo);
    document.getElementById('add-note-btn').addEventListener('click', () => openNoteEditor());
    document.getElementById('close-note-editor-btn').addEventListener('click', closeNoteEditor);
    document.getElementById('save-note-btn').addEventListener('click', handleSaveNote);
    document.getElementById('add-checklist-item-form').addEventListener('submit', handleAddChecklistItem);
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
                if (isNegative) {
                    stressSlider.value = Math.abs(currentStress) || 3;
                } else {
                    stressSlider.value = -(Math.abs(currentStress) || 3);
                }
                stressValueDisplay.textContent = stressSlider.value;
            }
        });
    });
    const selectedOption = group.querySelector('.radio-option.selected') || options[0];
    if (selectedOption) selectedOption.click();
}

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

async function skipTask(taskId) {
    if (!confirm('Mark this task as skipped? It will not count towards your progress.')) return;
    
    const result = await apiCall('/api/skip_task', 'POST', { task_id: taskId });
    if (result && result.success) {
        await fetchAndRenderTasks(currentSelectedDate);
        await fetchAndRenderStats();
    }
}

async function handleDateChange(e) {
    currentSelectedDate = e.target.value;
    const isToday = currentSelectedDate === new Date().toISOString().split('T')[0];
    
    document.getElementById('tasks-card-header').textContent = isToday ? "Today's Tasks" : `Tasks for ${currentSelectedDate}`;
    document.getElementById('narrative-card-header').textContent = isToday ? "Adventure Log" : `Log for ${currentSelectedDate}`;
    document.getElementById('daily-narrative-header').textContent = isToday ? "Today's Adventure" : `Adventure for ${currentSelectedDate}`;

    await fetchAndRenderTasks(currentSelectedDate);
    await fetchAndRenderDailyNarrative(currentSelectedDate);
    await fetchAndRenderDailyChecklist(currentSelectedDate);
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
        if (!payload.is_negative_habit && payload.attribute) await fetchAndRenderAttributes();
        await fetchAndRenderStats();
        await fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1);
        await fetchAndRenderHabitProgressor();
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
    const payload = {
        title: form.querySelector('#quest-title').value,
        description: form.querySelector('#quest-description').value,
        difficulty: form.querySelector('#quest-difficulty').value,
        attribute_focus: form.querySelector('#quest-attribute').value,
        due_date: form.querySelector('#quest-due-date').value || null,
    };
    const diffToXp = {"Easy": 50, "Medium": 100, "Hard": 175, "Epic": 250};
    payload.xp_reward = diffToXp[payload.difficulty] || 100;

    const result = await apiCall('/api/add_quest', 'POST', payload);
    if (result && result.success) {
        form.reset();
        toggleForm('add-quest-form-container');
        await fetchAndRenderQuests();
        await fetchAndRenderStats();
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

async function handleHabitProgressSelection(event) {
    const selectedHabit = event.target.value;
    const displayEl = document.getElementById('habit-progress-display');

    if (!selectedHabit) {
        displayEl.style.display = 'none';
        return;
    }

    const progressData = await apiCall(`/api/habit_progress?description=${encodeURIComponent(selectedHabit)}`);
    if (progressData) {
        renderHabitProgress(progressData);
        displayEl.style.display = 'block';
    }
}

async function completeTask(taskId, isNumeric = false, unit = '', forcedValue = null) {
    const taskElement = document.querySelector(`button[onclick*="completeTask(${taskId})"]`)?.closest('.task-item');
    if (taskElement) taskElement.style.opacity = '0.5';

    let payload = { task_id: taskId };

    if (forcedValue !== null) {
        payload.logged_numeric_value = forcedValue;
    } else if (isNumeric) {
        const loggedValue = prompt(`How many ${unit} did you log? (Enter number)`);
        if (loggedValue === null) {
            if (taskElement) taskElement.style.opacity = '1';
            return;
        }
        if (isNaN(parseFloat(loggedValue))) {
            alert('Invalid number entered. Please try again.');
            if (taskElement) taskElement.style.opacity = '1';
            return;
        }
        payload.logged_numeric_value = parseFloat(loggedValue);
    }

    const result = await apiCall('/api/complete_task', 'POST', payload);
    if (result && result.success) {
        await fetchAndRenderTasks(currentSelectedDate);
        await fetchAndRenderAttributes();
        await fetchAndRenderStats();
        await fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1);
        if (isNumeric) await fetchAndRenderHabitProgressor(true);
        
        if (Math.random() < 0.2) {
           await fetchAndRenderMilestones(milestones.page);
        }
    } else {
        if (taskElement) taskElement.style.opacity = '1';
    }
}

async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) return;
    const result = await apiCall('/api/delete_task', 'POST', { task_id: taskId });
    if (result && result.success) {
        await fetchAndRenderTasks(currentSelectedDate);
        const deletedTask = tasks.find(t => t.id === taskId);
        if (deletedTask && deletedTask.completed && !deletedTask.is_negative_habit) {
            await fetchAndRenderAttributes();
        }
        await fetchAndRenderStats();
        await fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1);
        await fetchAndRenderHabitProgressor();
    }
}

async function deleteRecurringTask(rtId) {
    if (!confirm('Delete this recurring habit permanently? This will not delete already generated tasks.')) return;
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
        await fetchAndRenderQuests();
        await fetchAndRenderAttributes();
        await fetchAndRenderStats();
        await fetchAndRenderMilestones(milestones.page);
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

// --- Quest Step Handlers ---
function openEditQuestModal(questId) {
    const quest = quests.find(q => q.id === questId);
    if (!quest) return;

    document.getElementById('edit-quest-id').value = quest.id;
    document.getElementById('edit-quest-title').value = quest.title;
    document.getElementById('edit-quest-description').value = quest.description;
    
    renderQuestChecklistInModal(quest);

    document.getElementById('editQuestModal').style.display = 'block';
}

function closeEditQuestModal() {
    document.getElementById('editQuestModal').style.display = 'none';
}

function renderQuestChecklistInModal(quest) {
    const container = document.getElementById('edit-quest-checklist-container');
    container.innerHTML = '';
    const checklist = document.createElement('ul');
    checklist.className = 'quest-checklist';

    if (quest.steps && quest.steps.length > 0) {
        quest.steps.forEach(step => {
            const stepEl = document.createElement('li');
            stepEl.className = `quest-step ${step.is_completed ? 'completed' : ''}`;
            stepEl.innerHTML = `
                <input type="checkbox" onchange="toggleQuestStep(${step.id})" ${step.is_completed ? 'checked' : ''}>
                <span class="quest-step-label">${step.description}</span>
                <span class="quest-step-delete-btn" onclick="deleteQuestStep(${step.id}, ${quest.id})">✖</span>
            `;
            checklist.appendChild(stepEl);
        });
    } else {
        checklist.innerHTML = '<p style="font-size: 0.9em; color: var(--text-light-color);">No steps added yet.</p>';
    }
    container.appendChild(checklist);
}

async function handleSaveQuestChanges() {
    const questId = document.getElementById('edit-quest-id').value;
    const payload = {
        title: document.getElementById('edit-quest-title').value,
        description: document.getElementById('edit-quest-description').value
    };

    const result = await apiCall(`/api/quests/${questId}`, 'PUT', payload);
    if (result && result.success) {
        closeEditQuestModal();
        await fetchAndRenderQuests();
    }
}

async function handleAddQuestStep(event) {
    event.preventDefault();
    const questId = document.getElementById('edit-quest-id').value;
    const descriptionInput = document.getElementById('new-quest-step-desc');
    const description = descriptionInput.value.trim();

    if (!description) return;

    const result = await apiCall(`/api/quests/${questId}/steps`, 'POST', { description });
    if (result && result.success) {
        descriptionInput.value = '';
        const quest = quests.find(q => q.id === parseInt(questId));
        if (quest) {
            quest.steps.push(result.step);
            renderQuestChecklistInModal(quest);
            await fetchAndRenderQuests();
        }
    }
}

async function toggleQuestStep(stepId) {
    const result = await apiCall(`/api/quest_steps/${stepId}/toggle`, 'PUT');
    if (result && result.success) {
        const quest = quests.find(q => q.steps.some(s => s.id === stepId));
        if(quest) {
            const step = quest.steps.find(s => s.id === stepId);
            step.is_completed = result.is_completed;
            renderQuestChecklistInModal(quest);
            await fetchAndRenderQuests();
        }
    }
}

async function deleteQuestStep(stepId, questId) {
    if (!confirm('Are you sure you want to delete this step?')) return;
    const result = await apiCall(`/api/quest_steps/${stepId}`, 'DELETE');
    if (result && result.success) {
        const quest = quests.find(q => q.id === questId);
        if (quest) {
            quest.steps = quest.steps.filter(s => s.id !== stepId);
            renderQuestChecklistInModal(quest);
            await fetchAndRenderQuests();
        }
    }
}

// --- Handlers for Credo, Notes, Daily Checklist ---
async function handleSaveCredo() {
    const content = document.getElementById('credo-content').value;
    const result = await apiCall('/api/credo', 'POST', { content });
    if (result && result.success) {
        alert('Credo saved!');
    }
}

function openNoteEditor(note = null) {
    const modal = document.getElementById('noteEditorModal');
    const title = document.getElementById('note-editor-title');
    const idInput = document.getElementById('note-editor-id');
    const titleInput = document.getElementById('note-title-input');
    const contentInput = document.getElementById('note-content-input');

    if (note) {
        title.textContent = 'Edit Note';
        idInput.value = note.id;
        titleInput.value = note.title;
        contentInput.value = note.content;
    } else {
        title.textContent = 'Add Note';
        idInput.value = '';
        titleInput.value = '';
        contentInput.value = '';
    }
    modal.style.display = 'block';
}

function closeNoteEditor() {
    document.getElementById('noteEditorModal').style.display = 'none';
}

async function handleSaveNote() {
    const id = document.getElementById('note-editor-id').value;
    const payload = {
        title: document.getElementById('note-title-input').value,
        content: document.getElementById('note-content-input').value
    };

    if (!payload.title) {
        alert('Title is required for a note.');
        return;
    }

    const endpoint = id ? `/api/notes/${id}` : '/api/notes';
    const method = id ? 'PUT' : 'POST';

    const result = await apiCall(endpoint, method, payload);
    if (result && result.success) {
        closeNoteEditor();
        await fetchAndRenderNotes();
    }
}

async function handleDeleteNote(noteId) {
    if (!confirm('Are you sure you want to delete this note?')) return;
    const result = await apiCall(`/api/notes/${noteId}`, 'DELETE');
    if (result && result.success) {
        await fetchAndRenderNotes();
    }
}

async function handleAddChecklistItem(event) {
    event.preventDefault();
    const input = document.getElementById('new-checklist-item-question');
    const question = input.value.trim();
    if (!question) return;

    const result = await apiCall('/api/daily_checklist_items', 'POST', { question });
    if (result && result.success) {
        input.value = '';
        await fetchAndRenderDailyChecklist(currentSelectedDate);
    }
}

async function handleLogChecklistItem(itemId, status) {
    const payload = {
        item_id: itemId,
        date: currentSelectedDate,
        status: status
    };
    await apiCall('/api/daily_checklist_logs', 'POST', payload);
    await fetchAndRenderDailyChecklist(currentSelectedDate);
}

async function handleDeleteChecklistItem(itemId) {
    if (!confirm('Are you sure you want to delete this daily checklist item permanently?')) return;
    const result = await apiCall(`/api/daily_checklist_items/${itemId}`, 'DELETE');
    if (result && result.success) {
        await fetchAndRenderDailyChecklist(currentSelectedDate);
    }
}

// --- API Call Abstraction ---
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

// --- Fetch & Render Functions ---
async function fetchAndRenderAttributes() {
    attributes = await apiCall('/api/attributes') || [];
    renderAttributes();
    populateAttributeDropdowns();
}

async function fetchAndRenderTasks(date) {
    tasks = await apiCall(`/api/tasks?date=${date}`) || [];
    renderTasks();
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
        renderDailyNarrative(data.narrative);
        if (forceRegenerate) {
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

async function fetchAndRenderHeatmap(year, month) {
    const data = await apiCall(`/api/heatmap?year=${year}&month=${month}`);
    if (data) {
        renderHeatmap(year, month, data);
    }
}

async function fetchAndRenderHabitProgressor(refreshCurrent = false) {
    const habitList = await apiCall('/api/get_numeric_habits');
    const selectEl = document.getElementById('habit-progress-select');
    const currentSelection = selectEl.value;
    
    if (habitList) {
        populateHabitProgressDropdown(habitList, currentSelection);
        if (refreshCurrent && currentSelection) {
            const progressData = await apiCall(`/api/habit_progress?description=${encodeURIComponent(currentSelection)}`);
            if (progressData) renderHabitProgress(progressData);
        }
    }
}

async function fetchAndRenderCredo() {
    const data = await apiCall('/api/credo');
    if (data) {
        document.getElementById('credo-content').value = data.content;
    }
}

async function fetchAndRenderNotes() {
    notes = await apiCall('/api/notes') || [];
    renderNotes();
}

async function fetchAndRenderDailyChecklist(date) {
    const data = await apiCall(`/api/daily_checklist_logs?date=${date}`);
    if (data) {
        renderDailyChecklist(data);
    }
}

// --- Render Functions ---
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
            attr.subskills.filter(sub => sub.total_xp > 0).forEach(sub => {
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

// CORRECTED RENDER TASKS FUNCTION
function renderTasks() {
    const container = document.getElementById('task-list');
    container.innerHTML = '';
    if (!tasks || tasks.length === 0) {
        container.innerHTML = '<li>No tasks for this day.</li>'; return;
    }
    tasks.forEach(task => {
        const taskEl = document.createElement('li');
        let taskClasses = 'task-item';
        
        if (task.completed) taskClasses += ' task-completed';
        if (task.skipped) taskClasses += ' task-skipped';
        if (task.is_negative_habit) taskClasses += ' negative-habit';
        
        taskEl.className = taskClasses;
        
        let attributeText = task.attribute ? `[${task.attribute}${task.subskill ? ` → ${task.subskill}`: ''}]` : '';
        let xpText = task.is_negative_habit ? `(Avoid: ${task.xp || 25} XP)` : `(${task.xp} XP)`;
        let numericText = '';

        if (task.numeric_unit) {
            if (task.completed && task.logged_numeric_value !== null) {
                let goalText = task.numeric_value !== null ? `(Goal: ${task.numeric_value} ${task.numeric_unit})` : '';
                numericText = `<span class="completion-status">Logged: ${task.logged_numeric_value} ${task.numeric_unit} ${goalText}</span>`;
            } else if (task.numeric_value !== null) {
                numericText = `(Goal: ${task.numeric_value} ${task.numeric_unit})`;
            } else {
                 numericText = `(${task.numeric_unit})`;
            }
        }
        
        let actionButtons = '';
        
        if (task.completed) {
            actionButtons = `<span class="completion-status">✓ Logged!</span>`;
        } else if (task.skipped) {
            actionButtons = '<span class="completion-status">⏭ Skipped</span>';
        } else if (task.is_negative_habit) {
            // THIS IS THE CORRECTED LOGIC FOR NEGATIVE HABITS
            if (task.numeric_unit && task.numeric_unit !== 'occurrence') {
                actionButtons = `<button onclick="completeTask(${task.id}, true, '${task.numeric_unit}')" class="btn-warning btn-small">📝 Log Habit</button>`;
            } else {
                actionButtons = `
                    <div class="task-actions negative-habit-actions">
                        <button onclick="completeTask(${task.id}, false, '', 1)" class="btn-danger btn-small">Yes, I did it</button>
                        <button onclick="completeTask(${task.id}, false, '', 0)" class="btn-success btn-small">No, I avoided it</button>
                    </div>
                `;
            }
        } else {
            const isNumeric = !!task.numeric_unit;
            actionButtons = `
                <button onclick="completeTask(${task.id}, ${isNumeric}, '${task.numeric_unit}')" class="btn-success btn-small">✓ Complete</button>
                <button onclick="skipTask(${task.id})" class="btn-warning btn-small">⏭ Skip</button>
            `;
        }
        
        taskEl.innerHTML = `
            <div>
                ${task.description} ${attributeText} ${xpText} ${numericText}
                <small>Stress Penalty: +${Math.abs(task.stress_effect)}</small>
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

    const statOrder = [
        'Total Tasks Completed', 'Tasks Remaining Today', 'Tasks Skipped Today',
        'Negative Habits Done', 'Negative Habits Avoided', 'Total XP',
        'Active Quests', 'Completed Quests'
    ];

    statOrder.forEach(statName => {
        if (characterStats.hasOwnProperty(statName)) {
            const statEl = document.createElement('div');
            statEl.className = 'stat-entry';
            let statValue = characterStats[statName];
            let style = (statName === 'Tasks Remaining Today' && statValue > 0) ? 
                ' style="color: var(--negative-color); font-weight: bold;"' : '';
            statEl.innerHTML = `<strong>${statName.replace(/([A-Z])/g, ' $1').trim()}:</strong> <span${style}>${statValue}</span>`;
            container.appendChild(statEl);
        }
    });

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
        el.className = `task-item ${rt.is_negative_habit ? 'negative-habit' : ''} ${!rt.is_active ? 'task-completed' : ''}`;
        let attributeText = rt.attribute_name ? `[${rt.attribute_name}]` : '';
        let numericText = rt.numeric_unit ? `(Goal: ${rt.numeric_value} ${rt.numeric_unit})` : '';
        el.innerHTML = `
            <div>
                ${rt.description} ${attributeText} ${numericText}
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
    card.className = `quest-card ${quest.status !== 'Active' ? 'quest-completed-card' : ''}`;
    card.id = `quest-card-${quest.id}`;
    
    let dueStatus = '';
    if (quest.status === 'Active' && quest.due_date) {
        const dueDate = new Date(quest.due_date + "T23:59:59");
        const today = new Date();
        const diffTime = dueDate - today;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        if (diffDays < 0) dueStatus = `<span style="color: var(--negative-color);">Overdue!</span>`;
        else if (diffDays <= 0) dueStatus = `<span style="color: var(--neutral-color);">Due Today!</span>`;
        else dueStatus = `Due in ${diffDays} day(s)`;
    } else if (quest.status === 'Completed') {
        dueStatus = `Completed: ${quest.completed_date}`;
    } else {
        dueStatus = 'No due date';
    }

    const completedSteps = quest.steps.filter(s => s.is_completed).length;
    const totalSteps = quest.steps.length;

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

        <div id="checklist-container-${quest.id}" class="quest-checklist-container">
             <ul class="quest-checklist">
                ${quest.steps.map(step => `
                    <li class="quest-step ${step.is_completed ? 'completed' : ''}">
                        <input type="checkbox" id="step-${step.id}" ${step.is_completed ? 'checked' : ''} disabled>
                        <label for="step-${step.id}" class="quest-step-label">${step.description}</label>
                    </li>
                `).join('')}
            </ul>
        </div>
        
        ${quest.status === 'Active' ? `
        <div class="quest-actions-bar">
            <button onclick="event.stopPropagation(); completeQuest(${quest.id})" class="btn-success btn-small">⚔ Complete Quest</button>
            <button onclick="event.stopPropagation(); openEditQuestModal(${quest.id})" class="btn-secondary btn-small">⚙️ Edit / View Steps</button>
            <span class="quest-progress-text">${totalSteps > 0 ? `${completedSteps}/${totalSteps} Steps` : 'No steps'}</span>
        </div>` : ''}
    `;

    card.addEventListener('click', (e) => {
        if (!e.target.closest('button')) {
            openEditQuestModal(quest.id);
        }
    });

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

function renderDailyNarrative(narrativeContent) {
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
        el.className = 'narrative-item';
        el.innerHTML = `
            <div class="narrative-date"><strong>${n.date}</strong></div>
            <div class="narrative-content">${n.narrative.replace(/\n/g, '<br>')}</div>
        `;
        container.appendChild(el);
    });
}

// CORRECTED RENDER HEATMAP
function renderHeatmap(year, month, data) {
    const container = document.getElementById('calendar-heatmap-display');
    container.innerHTML = '';
    if (!data) { container.innerHTML = '<p>Loading heatmap data...</p>'; return; }

    const activityMap = new Map(data.map(item => [item.date, { count: item.count, xp: item.xp }]));
    
    const xpValues = data.map(d => d.xp).filter(xp => xp > 0);
    const max_xp = xpValues.length > 0 ? Math.max(...xpValues) : 0;
    
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
                    
                    const currentXp = activity.xp;
                    if (max_xp > 0) {
                        if (currentXp > 0 && currentXp <= max_xp * 0.25) intensityLevel = 1;
                        else if (currentXp > max_xp * 0.25 && currentXp <= max_xp * 0.5) intensityLevel = 2;
                        else if (currentXp > max_xp * 0.5 && currentXp <= max_xp * 0.75) intensityLevel = 3;
                        else if (currentXp > max_xp * 0.75) intensityLevel = 4;
                    } else if (currentXp > 0) {
                        intensityLevel = 2;
                    }
                    
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

function renderHabitProgress(data) {
    const weekContainer = document.getElementById('habit-progress-week');
    const monthContainer = document.getElementById('habit-progress-month');
    const { unit, is_negative } = data;

    const progressHeader = document.getElementById('habit-progress-header');
    if (progressHeader) {
        let existingLabel = progressHeader.querySelector('.habit-goal-label');
        if (existingLabel) existingLabel.remove();
        progressHeader.textContent = 'Week-over-Week';
        
        if (is_negative) {
            const label = document.createElement('span');
            label.className = 'habit-goal-label';
            label.textContent = '(Goal: Lower is Better)';
            progressHeader.appendChild(label);
        }
    }

    const formatChange = (change) => {
        if (change > 0) return `<span class="progress-change positive">▲ ${change}%</span>`;
        if (change < 0) return `<span class="progress-change negative">▼ ${Math.abs(change)}%</span>`;
        return `<span class="progress-change neutral">--</span>`;
    };

    weekContainer.innerHTML = `
        <div class="progress-period">
            <h5>Last Week</h5>
            <div class="progress-stat">Total: <span class="value">${data.week.last_week.total.toFixed(1)}</span> ${unit}</div>
            <div class="progress-stat">Daily Avg: <span class="value">${data.week.last_week.avg.toFixed(1)}</span> ${unit}</div>
        </div>
        <div class="progress-period">
            <h5>This Week</h5>
            <div class="progress-stat">Total: <span class="value">${data.week.this_week.total.toFixed(1)}</span> ${unit} ${formatChange(data.week.total_change)}</div>
            <div class="progress-stat">Daily Avg: <span class="value">${data.week.this_week.avg.toFixed(1)}</span> ${unit} ${formatChange(data.week.avg_change)}</div>
        </div>
    `;

    monthContainer.innerHTML = `
        <div class="progress-period">
            <h5>Last Month</h5>
            <div class="progress-stat">Total: <span class="value">${data.month.last_month.total.toFixed(1)}</span> ${unit}</div>
            <div class="progress-stat">Daily Avg: <span class="value">${data.month.last_month.avg.toFixed(1)}</span> ${unit}</div>
        </div>
        <div class="progress-period">
            <h5>This Month</h5>
            <div class="progress-stat">Total: <span class="value">${data.month.this_month.total.toFixed(1)}</span> ${unit} ${formatChange(data.month.total_change)}</div>
            <div class="progress-stat">Daily Avg: <span class="value">${data.month.this_month.avg.toFixed(1)}</span> ${unit} ${formatChange(data.month.avg_change)}</div>
        </div>
    `;
}

function renderNotes() {
    const container = document.getElementById('notes-list-container');
    container.innerHTML = '';
    if (!notes || notes.length === 0) {
        container.innerHTML = '<p>No notes yet. Add one to get started!</p>';
        return;
    }

    notes.forEach(note => {
        const noteEl = document.createElement('div');
        noteEl.className = 'note-item';
        // Use JSON.stringify to safely embed the note object for editing
        const noteData = JSON.stringify(note).replace(/"/g, '"');
        noteEl.innerHTML = `
            <div class="note-item-header">
                <strong>${note.title}</strong>
                <div class="note-actions">
                    <button class="btn-secondary btn-small" onclick='openNoteEditor(${noteData})'>Edit</button>
                    <button class="btn-danger btn-small" onclick="handleDeleteNote(${note.id})">Delete</button>
                </div>
            </div>
            <p>${note.content.substring(0, 100)}${note.content.length > 100 ? '...' : ''}</p>
            <small>Last updated: ${note.updated_at}</small>
        `;
        container.appendChild(noteEl);
    });
}

function renderDailyChecklist(items) {
    const container = document.getElementById('daily-checklist-container');
    container.innerHTML = '';
    if (!items || items.length === 0) {
        container.innerHTML = '<p>Add a daily question below to start your review.</p>';
        return;
    }

    items.forEach(item => {
        const itemEl = document.createElement('div');
        itemEl.className = 'daily-checklist-item';
        itemEl.innerHTML = `
            <span>${item.question}</span>
            <div class="checklist-actions">
                <button class="btn-success btn-small ${item.status === 'completed' ? 'active' : ''}" onclick="handleLogChecklistItem(${item.id}, 'completed')">✓</button>
                <button class="btn-danger btn-small ${item.status === 'missed' ? 'active' : ''}" onclick="handleLogChecklistItem(${item.id}, 'missed')">✗</button>
                <button class="btn-secondary btn-small" onclick="handleDeleteChecklistItem(${item.id})">🗑️</button>
            </div>
        `;
        container.appendChild(itemEl);
    });
}

// --- Utility and Helper Functions ---
function populateAttributeDropdowns() {
    const attributeSelects = ['task-attribute', 'recurring-task-attribute', 'quest-attribute'];
    attributeSelects.forEach(selectId => {
        const selectElement = document.getElementById(selectId);
        if (!selectElement) return;
        
        const firstOptionValue = selectElement.options[0]?.value;
        selectElement.innerHTML = '';
        
        if (firstOptionValue !== undefined) {
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

function populateHabitProgressDropdown(habitList, currentSelection) {
    const selectEl = document.getElementById('habit-progress-select');
    selectEl.innerHTML = '';

    if (!habitList || habitList.length === 0) {
        selectEl.innerHTML = '<option value="">-- No numeric habits tracked yet --</option>';
        document.getElementById('habit-progress-display').style.display = 'none';
        return;
    }

    const placeholder = document.createElement('option');
    placeholder.value = "";
    placeholder.textContent = "-- Select a habit --";
    selectEl.appendChild(placeholder);

    habitList.forEach(habit => {
        const option = document.createElement('option');
        option.value = habit;
        option.textContent = habit;
        if (habit === currentSelection) {
            option.selected = true;
        }
        selectEl.appendChild(option);
    });
}

// CORRECTED PAGINATION FUNCTION
function renderPagination(containerId, infoContainerId, pageDataObject, fetchCallback) {
    const container = document.getElementById(containerId);
    const infoContainer = document.getElementById(infoContainerId);
    if(container) container.innerHTML = '';
    if(infoContainer) infoContainer.innerHTML = '';

    if (!pageDataObject || pageDataObject.totalPages <= 1) return;

    if (pageDataObject.page > 1) {
        const prevBtn = document.createElement('button');
        prevBtn.innerHTML = '« Prev';
        prevBtn.className = 'btn-secondary btn-small';
        prevBtn.onclick = () => fetchCallback(pageDataObject.page - 1);
        container.appendChild(prevBtn);
    }
    
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
    if (infoContainer) infoContainer.textContent = `Showing page ${pageDataObject.page} of ${pageDataObject.totalPages}.`;
}

const tooltipElement = document.getElementById('tooltip');
function showTooltip(event, text) {
    if (!tooltipElement) return;
    tooltipElement.innerHTML = text;
    tooltipElement.style.display = 'block';
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

function updateHeatmapControlsLabel() {
    const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    document.getElementById('current-heatmap-month-year').textContent = `${monthNames[heatmapCurrentDate.getMonth()]} ${heatmapCurrentDate.getFullYear()}`;
}

function navigateHeatmapMonth(direction) {
    heatmapCurrentDate.setMonth(heatmapCurrentDate.getMonth() + direction);
    updateHeatmapControlsLabel();
    fetchAndRenderHeatmap(heatmapCurrentDate.getFullYear(), heatmapCurrentDate.getMonth() + 1);
}
