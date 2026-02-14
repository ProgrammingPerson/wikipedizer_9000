/**
 * Wikipedizer 9000 - Science Olympiad 2026
 * Frontend JavaScript for the astronomy research scraper
 */

// ═══════════════════════════════════════════════════════════════════════════════
// STATE MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════════

let categories = {};
let selectedCategories = {};
let currentStep = 1;
let currentJobId = null;

// ═══════════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
    await loadCategories();
    setupSourceCards();
    updateTopicCount();
});

async function loadCategories() {
    try {
        const response = await fetch('/api/categories');
        categories = await response.json();
        renderCategories();
    } catch (error) {
        console.error('Failed to load categories:', error);
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// CATEGORY RENDERING
// ═══════════════════════════════════════════════════════════════════════════════

function renderCategories() {
    const container = document.getElementById('categories-container');
    container.innerHTML = '';
    
    Object.entries(categories).forEach(([key, data]) => {
        const topics = data.topics || data;
        const description = data.description || '';
        
        const card = document.createElement('div');
        card.className = 'category-card';
        card.dataset.category = key;
        
        card.innerHTML = `
            <div class="category-header" onclick="toggleCategory('${key}')">
                <div class="category-info">
                    <h3>${formatCategoryName(key)}</h3>
                    <p>${description}</p>
                </div>
                <div class="category-toggle">
                    <span class="topic-count">${topics.length} topics</span>
                    <div class="category-checkbox">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                            <path d="M5 12l5 5L20 7"/>
                        </svg>
                    </div>
                </div>
            </div>
            <div class="category-topics">
                <div class="topic-list">
                    ${topics.map(topic => `
                        <label class="topic-chip" data-topic="${topic}" onclick="event.stopPropagation(); toggleTopic('${key}', '${escapeHtml(topic)}')">
                            <div class="chip-check">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                                    <path d="M5 12l5 5L20 7"/>
                                </svg>
                            </div>
                            <span>${topic}</span>
                        </label>
                    `).join('')}
                </div>
            </div>
        `;
        
        container.appendChild(card);
    });
}

function formatCategoryName(key) {
    return key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/'/g, "\\'");
}

// ═══════════════════════════════════════════════════════════════════════════════
// CATEGORY & TOPIC SELECTION
// ═══════════════════════════════════════════════════════════════════════════════

function toggleCategory(categoryKey) {
    const card = document.querySelector(`.category-card[data-category="${categoryKey}"]`);
    const isSelected = card.classList.contains('selected');
    const topics = categories[categoryKey].topics || categories[categoryKey];
    
    if (isSelected) {
        // Deselect all topics in category
        card.classList.remove('selected');
        delete selectedCategories[categoryKey];
        
        card.querySelectorAll('.topic-chip').forEach(chip => {
            chip.classList.remove('selected');
        });
    } else {
        // Select all topics in category
        card.classList.add('selected');
        selectedCategories[categoryKey] = [...topics];
        
        card.querySelectorAll('.topic-chip').forEach(chip => {
            chip.classList.add('selected');
        });
    }
    
    // Toggle expanded state
    card.classList.toggle('expanded');
    
    updateTopicCount();
}

function toggleTopic(categoryKey, topic) {
    const card = document.querySelector(`.category-card[data-category="${categoryKey}"]`);
    const chip = card.querySelector(`.topic-chip[data-topic="${topic}"]`);
    
    if (!selectedCategories[categoryKey]) {
        selectedCategories[categoryKey] = [];
    }
    
    const index = selectedCategories[categoryKey].indexOf(topic);
    
    if (index > -1) {
        // Remove topic
        selectedCategories[categoryKey].splice(index, 1);
        chip.classList.remove('selected');
        
        // Remove category if no topics selected
        if (selectedCategories[categoryKey].length === 0) {
            delete selectedCategories[categoryKey];
            card.classList.remove('selected');
        }
    } else {
        // Add topic
        selectedCategories[categoryKey].push(topic);
        chip.classList.add('selected');
        card.classList.add('selected');
    }
    
    updateTopicCount();
}

function selectAll() {
    Object.entries(categories).forEach(([key, data]) => {
        const topics = data.topics || data;
        const card = document.querySelector(`.category-card[data-category="${key}"]`);
        
        selectedCategories[key] = [...topics];
        card.classList.add('selected');
        
        card.querySelectorAll('.topic-chip').forEach(chip => {
            chip.classList.add('selected');
        });
    });
    
    updateTopicCount();
}

function deselectAll() {
    selectedCategories = {};
    
    document.querySelectorAll('.category-card').forEach(card => {
        card.classList.remove('selected');
        card.querySelectorAll('.topic-chip').forEach(chip => {
            chip.classList.remove('selected');
        });
    });
    
    updateTopicCount();
}

function updateTopicCount() {
    const count = Object.values(selectedCategories).reduce(
        (sum, topics) => sum + topics.length, 0
    );
    document.getElementById('topic-count').textContent = count;
}

// ═══════════════════════════════════════════════════════════════════════════════
// SOURCE SELECTION
// ═══════════════════════════════════════════════════════════════════════════════

function setupSourceCards() {
    document.querySelectorAll('.source-card').forEach(card => {
        card.addEventListener('click', () => {
            card.classList.toggle('selected');
            const checkbox = card.querySelector('input');
            checkbox.checked = card.classList.contains('selected');
        });
    });
}

function getSelectedSources() {
    return Array.from(document.querySelectorAll('.source-card.selected'))
        .map(card => card.dataset.source);
}

// ═══════════════════════════════════════════════════════════════════════════════
// STEP NAVIGATION
// ═══════════════════════════════════════════════════════════════════════════════

function goToStep(step) {
    // Validate before moving forward
    if (step === 2 && Object.keys(selectedCategories).length === 0) {
        alert('Please select at least one topic to continue.');
        return;
    }
    
    // Update step indicators
    document.querySelectorAll('.step').forEach((el, index) => {
        el.classList.remove('active', 'completed');
        if (index + 1 < step) {
            el.classList.add('completed');
        } else if (index + 1 === step) {
            el.classList.add('active');
        }
    });
    
    // Update panels
    document.querySelectorAll('.panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    const panelIds = ['panel-topics', 'panel-sources', 'panel-progress'];
    document.getElementById(panelIds[step - 1]).classList.add('active');
    
    currentStep = step;
}

// ═══════════════════════════════════════════════════════════════════════════════
// SCRAPING
// ═══════════════════════════════════════════════════════════════════════════════

async function startScraping() {
    const sources = getSelectedSources();
    
    if (sources.length === 0) {
        alert('Please select at least one source.');
        return;
    }
    
    // Prepare categories data
    const categoriesData = {};
    Object.entries(selectedCategories).forEach(([key, topics]) => {
        categoriesData[key] = {
            description: categories[key].description || '',
            topics: topics
        };
    });
    
    // Move to progress step
    goToStep(3);
    
    try {
        // Start the scraping job
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                categories: categoriesData,
                sources: sources
            })
        });
        
        const data = await response.json();
        currentJobId = data.job_id;
        
        // Start listening for progress updates
        listenForProgress(currentJobId);
        
    } catch (error) {
        console.error('Failed to start scraping:', error);
        document.getElementById('status-text').textContent = 'Error starting job';
    }
}

function listenForProgress(jobId) {
    const eventSource = new EventSource(`/api/progress/${jobId}`);
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.heartbeat) {
            return; // Ignore heartbeats
        }
        
        updateProgressUI(data);
        
        if (data.status === 'complete') {
            eventSource.close();
            showDownloadSection();
        } else if (data.status === 'error') {
            eventSource.close();
            showError(data.error);
        }
    };
    
    eventSource.onerror = () => {
        eventSource.close();
        // Check if job is actually complete
        checkJobStatus(jobId);
    };
}

function updateProgressUI(data) {
    // Update progress ring
    const progress = data.progress || 0;
    const circumference = 326.7; // 2 * PI * 52
    const offset = circumference - (progress / 100) * circumference;
    
    const ring = document.getElementById('progress-ring');
    ring.style.strokeDashoffset = offset;
    
    document.getElementById('progress-percentage').textContent = 
        Math.round(progress) + '%';
    
    // Update stats
    document.getElementById('current-topic').textContent = 
        data.current_topic || 'Initializing...';
    document.getElementById('current-source').textContent = 
        data.current_source || '-';
    document.getElementById('completed-count').textContent = 
        data.completed_topics || 0;
    document.getElementById('total-count').textContent = 
        data.total_topics || 0;
    document.getElementById('files-count').textContent = 
        data.files_count || 0;
    
    // Update status text
    const statusMap = {
        'initializing': 'Initializing...',
        'starting': 'Starting scraper...',
        'fetching': 'Fetching content...',
        'processing': 'Processing topics...',
        'complete': 'Complete!'
    };
    document.getElementById('status-text').textContent = 
        statusMap[data.status] || 'Processing...';
}

function checkJobStatus(jobId) {
    // SSE disconnected - this is usually transient, user can refresh if needed
    console.log('SSE connection closed for job:', jobId);
}

function showDownloadSection() {
    document.getElementById('download-section').style.display = 'block';
    document.getElementById('progress-footer').style.display = 'none';
    document.getElementById('complete-footer').style.display = 'flex';
    
    // Update status indicator
    const statusDot = document.querySelector('.status-dot');
    if (statusDot) {
        statusDot.classList.remove('active');
        statusDot.style.background = 'var(--accent-success)';
    }
}

function showError(error) {
    document.getElementById('status-text').textContent = `Error: ${error}`;
    const statusDot = document.querySelector('.status-dot');
    if (statusDot) {
        statusDot.classList.remove('active');
        statusDot.style.background = 'var(--accent-warning)';
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// DOWNLOAD
// ═══════════════════════════════════════════════════════════════════════════════

function downloadResults() {
    if (!currentJobId) {
        alert('No job ID found');
        return;
    }
    
    // Trigger download
    window.location.href = `/api/download/${currentJobId}`;
}

function downloadTextFile() {
    if (!currentJobId) {
        alert('No job ID found');
        return;
    }
    
    // Trigger download
    window.location.href = `/api/download-text/${currentJobId}`;
}

// ═══════════════════════════════════════════════════════════════════════════════
// RESET
// ═══════════════════════════════════════════════════════════════════════════════

async function resetApp() {
    // Clean up job on server
    if (currentJobId) {
        try {
            await fetch(`/api/cleanup/${currentJobId}`, { method: 'POST' });
        } catch (error) {
            console.error('Cleanup failed:', error);
        }
    }
    
    // Reset state
    currentJobId = null;
    selectedCategories = {};
    
    // Reset UI
    deselectAll();
    
    // Reset progress UI
    document.getElementById('progress-ring').style.strokeDashoffset = 326.7;
    document.getElementById('progress-percentage').textContent = '0%';
    document.getElementById('current-topic').textContent = 'Initializing...';
    document.getElementById('current-source').textContent = '-';
    document.getElementById('completed-count').textContent = '0';
    document.getElementById('total-count').textContent = '0';
    document.getElementById('files-count').textContent = '0';
    document.getElementById('status-text').textContent = 'Processing...';
    
    // Reset sections
    document.getElementById('download-section').style.display = 'none';
    document.getElementById('progress-footer').style.display = 'flex';
    document.getElementById('complete-footer').style.display = 'none';
    
    // Reset Drive UI
    const driveStatus = document.getElementById('drive-upload-status');
    const driveSuccess = document.getElementById('drive-success');
    const driveBtn = document.getElementById('btn-upload-drive');
    if (driveStatus) driveStatus.style.display = 'none';
    if (driveSuccess) driveSuccess.style.display = 'none';
    if (driveBtn) {
        driveBtn.disabled = false;
        const btnText = document.getElementById('drive-btn-text');
        if (btnText) btnText.textContent = 'Save to Google Drive';
    }
    
    // Reset status dot
    const statusDot = document.querySelector('.status-dot');
    if (statusDot) {
        statusDot.classList.add('active');
        statusDot.style.background = '';
    }
    
    // Re-select all sources
    document.querySelectorAll('.source-card').forEach(card => {
        card.classList.add('selected');
        card.querySelector('input').checked = true;
    });
    
    // Go back to step 1
    goToStep(1);
}

// ═══════════════════════════════════════════════════════════════════════════════
// GOOGLE DRIVE INTEGRATION
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Show the Drive options modal
 */
function showDriveOptions() {
    const modal = document.getElementById('drive-options-modal');
    if (modal) {
        modal.style.display = 'flex';
        
        // Set default folder name with date
        const folderInput = document.getElementById('drive-folder-name');
        if (folderInput && !folderInput.value) {
            folderInput.value = `Astronomy_Notes_${new Date().toISOString().split('T')[0]}`;
        }
    }
}

/**
 * Hide the Drive options modal
 */
function hideDriveOptions() {
    const modal = document.getElementById('drive-options-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Disconnect from Google Drive
 */
async function disconnectDrive() {
    if (!confirm('Disconnect from Google Drive?')) {
        return;
    }
    
    try {
        const response = await fetch('/oauth/google/disconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (response.ok) {
            // Reload the page to update the UI
            window.location.reload();
        }
    } catch (error) {
        console.error('Failed to disconnect:', error);
        alert('Failed to disconnect from Google Drive');
    }
}

/**
 * Upload current job results to Google Drive
 */
async function uploadToDrive() {
    if (!currentJobId) {
        alert('No job results available');
        return;
    }
    
    // Get folder name from input
    const folderInput = document.getElementById('drive-folder-name');
    const folderName = folderInput?.value || `Astronomy_Notes_${new Date().toISOString().split('T')[0]}`;
    
    // Hide modal
    hideDriveOptions();
    
    const driveBtn = document.getElementById('btn-upload-drive');
    const driveStatus = document.getElementById('drive-upload-status');
    const driveSuccess = document.getElementById('drive-success');
    const driveBtnText = document.getElementById('drive-btn-text');
    
    // Disable button and show loading
    if (driveBtn) driveBtn.disabled = true;
    if (driveBtnText) driveBtnText.textContent = 'Uploading...';
    if (driveStatus) driveStatus.style.display = 'block';
    if (driveSuccess) driveSuccess.style.display = 'none';
    
    try {
        const response = await fetch(`/api/drive/upload/${currentJobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder_name: folderName
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            // Check if authentication is needed
            if (data.needs_auth) {
                // Redirect to Google auth
                window.location.href = '/oauth/google/authorize';
                return;
            }
            throw new Error(data.error || 'Upload failed');
        }
        
        // Show success
        if (driveStatus) driveStatus.style.display = 'none';
        if (driveSuccess) driveSuccess.style.display = 'flex';
        if (driveBtnText) driveBtnText.textContent = 'Saved to Drive!';
        
        // Set folder link if available
        const folderLink = document.getElementById('drive-folder-link');
        if (folderLink && data.folder_link) {
            folderLink.href = data.folder_link;
            folderLink.textContent = `Open "${data.folder_name}" in Drive`;
        } else if (folderLink) {
            folderLink.href = 'https://drive.google.com';
            folderLink.textContent = 'Open Google Drive';
        }
        
    } catch (error) {
        console.error('Drive upload failed:', error);
        
        // Show error state
        if (driveStatus) driveStatus.style.display = 'none';
        if (driveBtn) driveBtn.disabled = false;
        if (driveBtnText) driveBtnText.textContent = 'Save to Google Drive';
        
        alert('Failed to upload to Google Drive: ' + error.message);
    }
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('drive-options-modal');
    if (modal && e.target === modal) {
        hideDriveOptions();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideDriveOptions();
    }
});
