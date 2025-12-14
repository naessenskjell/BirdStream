/**
 * BirdStream - Advanced Dashboard Frontend
 * Phase 4: Real-time monitoring with WebSocket
 * 
 * Features:
 * - Real-time stream status updates via WebSocket
 * - Performance metrics and bandwidth graphs
 * - Live log viewer with filtering
 * - Image management interface
 * - YouTube settings configuration
 */

// WebSocket connection
let socket = null;
let isConnected = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;

// UI State
const uiState = {
    currentTab: 'status',
    autoRefresh: true,
    refreshInterval: 1000,
    metrics: {
        videoBitrate: [],
        audioBitrate: [],
        frameCount: [],
        timestamps: []
    },
    logs: [],
    images: [],
    maxDataPoints: 60
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeUI();
    connectWebSocket();
    initPreview();
});

/**
 * Initialize UI components and event listeners
 */
function initializeUI() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });
    
    // Mode control buttons
    document.getElementById('btn-live-mode')?.addEventListener('click', () => setStreamMode('live'));
    document.getElementById('btn-static-mode')?.addEventListener('click', () => setStreamMode('static'));
    document.getElementById('btn-off-mode')?.addEventListener('click', () => setStreamMode('off'));
    
    // Settings
    document.getElementById('btn-save-youtube-key')?.addEventListener('click', saveYouTubeKey);
    document.getElementById('btn-test-youtube')?.addEventListener('click', testYouTubeConnection);
    
    // Image management
    document.getElementById('image-upload')?.addEventListener('change', handleImageUpload);
    document.getElementById('btn-upload-image')?.addEventListener('click', () => {
        document.getElementById('image-upload').click();
    });
    
    // Log filtering
    document.getElementById('log-filter')?.addEventListener('change', function() {
        filterLogs(this.value);
    });
    document.getElementById('btn-clear-logs')?.addEventListener('click', clearLogs);
    
    // Auto-refresh toggle
    document.getElementById('toggle-auto-refresh')?.addEventListener('change', function() {
        uiState.autoRefresh = this.checked;
    });
    
    logger.info('UI initialized');
}

/**
 * WebSocket Connection Management
 */
function connectWebSocket() {
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}`;
        
        socket = io(url, {
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: MAX_RECONNECT_ATTEMPTS,
            transports: ['websocket', 'polling']
        });
        
        socket.on('connect', onSocketConnect);
        socket.on('disconnect', onSocketDisconnect);
        socket.on('error', onSocketError);
        socket.on('realtime_update', onRealtimeUpdate);
        socket.on('status_update', onStatusUpdate);
        socket.on('metrics_update', onMetricsUpdate);
        socket.on('logs_update', onLogsUpdate);
        socket.on('images_update', onImagesUpdate);
        socket.on('stream_state', onStreamStateChange);
        socket.on('error', onError);
        
        logger.info('WebSocket connection initiated');
    } catch (error) {
        logger.error(`WebSocket connection error: ${error.message}`);
        fallbackToPoll();
    }
}

function onSocketConnect() {
    isConnected = true;
    reconnectAttempts = 0;
    updateConnectionStatus(true);
    logger.info('Connected to server via WebSocket');
    
    // Request initial data
    if (socket) {
        socket.emit('request_status');
        socket.emit('request_metrics');
        socket.emit('request_logs', { count: 50 });
        socket.emit('request_images');
    }
}

function onSocketDisconnect() {
    isConnected = false;
    updateConnectionStatus(false);
    logger.warn('Disconnected from server');
}

function onSocketError(error) {
    logger.error(`Socket error: ${error}`);
}

function onRealtimeUpdate(data) {
    updateStatusPanel(data);
    updateMetricsData(data);
}

function onStatusUpdate(data) {
    updateStatusPanel(data);
}

function onMetricsUpdate(data) {
    updateMetricsDisplay(data);
}

function onLogsUpdate(data) {
    uiState.logs = data.logs || [];
    displayLogs();
}

function onImagesUpdate(data) {
    uiState.images = data.images || [];
    displayImages();
}

function onStreamStateChange(data) {
    updateStreamStateIndicator(data.state);
}

function onError(data) {
    showNotification(data.message || 'An error occurred', 'error');
    logger.error(data.message);
}

/**
 * Tab Management
 */
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
    });
    
    // Remove active state from buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tabElement = document.getElementById(`tab-${tabName}`);
    if (tabElement) {
        tabElement.style.display = 'block';
    }
    
    // Mark button as active
    const btn = document.querySelector(`[data-tab="${tabName}"]`);
    if (btn) {
        btn.classList.add('active');
    }
    
    uiState.currentTab = tabName;
    logger.info(`Switched to tab: ${tabName}`);
    
    // Request fresh data for tab
    if (tabName === 'metrics' && socket) {
        socket.emit('request_metrics');
    } else if (tabName === 'logs' && socket) {
        socket.emit('request_logs', { count: 100 });
    } else if (tabName === 'images' && socket) {
        socket.emit('request_images');
    }
}

/**
 * Status Panel Updates
 */
function updateStatusPanel(data) {
    const statusPanel = document.getElementById('status-panel');
    if (!statusPanel) return;
    
    const state = data.stream_state || 'unknown';
    const videoOk = data.video_ok ? '✓ OK' : '✗ Offline';
    const audioOk = data.audio_ok ? '✓ OK' : '✗ Offline';
    
    statusPanel.innerHTML = `
        <div class="status-item">
            <label>Stream State:</label>
            <span class="state-badge state-${state}">${state.toUpperCase()}</span>
        </div>
        <div class="status-item">
            <label>Video:</label>
            <span class="status-${data.video_ok ? 'ok' : 'offline'}">${videoOk}</span>
        </div>
        <div class="status-item">
            <label>Audio:</label>
            <span class="status-${data.audio_ok ? 'ok' : 'offline'}">${audioOk}</span>
        </div>
        <div class="status-item">
            <label>Active Streams:</label>
            <span>${data.active_streams || 0}</span>
        </div>
        <div class="status-item">
            <label>Updated:</label>
            <span>${new Date(data.timestamp).toLocaleTimeString()}</span>
        </div>
    `;
    
    updateStreamStateIndicator(state);
}

function updateStreamStateIndicator(state) {
    const indicator = document.getElementById('stream-state-indicator');
    if (indicator) {
        indicator.className = `stream-indicator state-${state}`;
        indicator.textContent = state.toUpperCase();
    }
}

/**
 * Metrics Display and Charting
 */
function updateMetricsData(data) {
    const now = new Date();
    const timestamp = now.getHours().toString().padStart(2, '0') + ':' +
                     now.getMinutes().toString().padStart(2, '0') + ':' +
                     now.getSeconds().toString().padStart(2, '0');
    
    // Store metrics with rolling window
    uiState.metrics.timestamps.push(timestamp);
    uiState.metrics.videoBitrate.push(data.video_bitrate || 0);
    uiState.metrics.audioBitrate.push(data.audio_bitrate || 0);
    uiState.metrics.frameCount.push(data.video_frames || 0);
    
    // Keep only last N data points
    while (uiState.metrics.timestamps.length > uiState.maxDataPoints) {
        uiState.metrics.timestamps.shift();
        uiState.metrics.videoBitrate.shift();
        uiState.metrics.audioBitrate.shift();
        uiState.metrics.frameCount.shift();
    }
    
    updateMetricsDisplay(data);
}

function updateMetricsDisplay(data) {
    const metricsPanel = document.getElementById('metrics-panel');
    if (!metricsPanel) return;
    
    const videoBitrate = data.video?.estimated_bitrate_kbps?.toFixed(2) || '0';
    const audioBitrate = data.audio?.estimated_bitrate_kbps?.toFixed(2) || '0';
    
    metricsPanel.innerHTML = `
        <div class="metrics-item">
            <label>Video Bitrate:</label>
            <span>${videoBitrate} kbps</span>
        </div>
        <div class="metrics-item">
            <label>Audio Bitrate:</label>
            <span>${audioBitrate} kbps</span>
        </div>
        <div class="metrics-item">
            <label>Video Frames:</label>
            <span>${data.video?.frames || 0}</span>
        </div>
        <div class="metrics-item">
            <label>Audio Frames:</label>
            <span>${data.audio?.frames || 0}</span>
        </div>
        <div class="metrics-item">
            <label>Reconnections:</label>
            <span>${data.stream?.reconnections || 0}</span>
        </div>
        <div class="metrics-item">
            <label>Fallbacks:</label>
            <span>${data.stream?.fallbacks || 0}</span>
        </div>
    `;
}

/**
 * Log Display and Management
 */
function displayLogs() {
    const logsPanel = document.getElementById('logs-panel');
    if (!logsPanel || !uiState.logs || uiState.logs.length === 0) {
        if (logsPanel) logsPanel.innerHTML = '<p>No logs available</p>';
        return;
    }
    
    const logsHTML = uiState.logs
        .slice(-50)  // Show last 50
        .reverse()   // Newest first
        .map(log => `
            <div class="log-entry log-${log.level?.toLowerCase() || 'info'}">
                <span class="log-time">${new Date(log.timestamp).toLocaleTimeString()}</span>
                <span class="log-type">[${log.type || 'general'}]</span>
                <span class="log-message">${log.message || ''}</span>
            </div>
        `)
        .join('');
    
    logsPanel.innerHTML = logsHTML;
}

function filterLogs(type) {
    if (!type) {
        displayLogs();
        return;
    }
    
    const logsPanel = document.getElementById('logs-panel');
    if (!logsPanel) return;
    
    const filtered = uiState.logs.filter(log => log.type === type);
    
    if (filtered.length === 0) {
        logsPanel.innerHTML = `<p>No logs of type "${type}"</p>`;
        return;
    }
    
    const logsHTML = filtered
        .slice(-50)
        .reverse()
        .map(log => `
            <div class="log-entry log-${log.level?.toLowerCase() || 'info'}">
                <span class="log-time">${new Date(log.timestamp).toLocaleTimeString()}</span>
                <span class="log-type">[${log.type}]</span>
                <span class="log-message">${log.message}</span>
            </div>
        `)
        .join('');
    
    logsPanel.innerHTML = logsHTML;
}

function clearLogs() {
    uiState.logs = [];
    displayLogs();
    showNotification('Logs cleared', 'info');
}

/**
 * Image Management
 */
function displayImages() {
    const imagesPanel = document.getElementById('images-panel');
    if (!imagesPanel) return;
    
    if (!uiState.images || uiState.images.length === 0) {
        imagesPanel.innerHTML = '<p>No images uploaded yet</p>';
        return;
    }
    
    const imagesHTML = uiState.images.map(image => `
        <div class="image-item">
            <img src="/static/images/${image.filename}" alt="${image.name}">
            <div class="image-info">
                <p>${image.name || image.filename}</p>
                <small>${new Date(image.uploaded).toLocaleString()}</small>
            </div>
            <div class="image-actions">
                <button onclick="selectImage('${image.id}')" class="btn-small">Select</button>
                <button onclick="deleteImage('${image.id}')" class="btn-small btn-danger">Delete</button>
            </div>
        </div>
    `).join('');
    
    imagesPanel.innerHTML = imagesHTML;
}

function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    if (file.size > 10 * 1024 * 1024) {
        showNotification('Image must be smaller than 10MB', 'error');
        return;
    }
    
    uploadImage(file);
}

function uploadImage(file) {
    const formData = new FormData();
    formData.append('image', file);
    
    fetch('/api/images/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok') {
            showNotification('Image uploaded successfully', 'success');
            if (socket) socket.emit('request_images');
        } else {
            showNotification(`Upload failed: ${data.message}`, 'error');
        }
    })
    .catch(error => {
        logger.error(`Upload error: ${error.message}`);
        showNotification('Upload failed', 'error');
    });
}

function selectImage(imageId) {
    fetch(`/api/images/${imageId}/select`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            showNotification('Image selected', 'success');
            if (socket) socket.emit('request_images');
        })
        .catch(error => showNotification('Failed to select image', 'error'));
}

function deleteImage(imageId) {
    if (!confirm('Delete this image?')) return;
    
    fetch(`/api/images/${imageId}`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            showNotification('Image deleted', 'success');
            if (socket) socket.emit('request_images');
        })
        .catch(error => showNotification('Failed to delete image', 'error'));
}

/**
 * Stream Control
 */
function setStreamMode(mode) {
    if (!socket) return;
    
    fetch('/api/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: mode })
    })
    .then(response => response.json())
    .then(data => {
        showNotification(`Stream mode set to ${mode}`, 'success');
        socket.emit('request_status');
    })
    .catch(error => showNotification('Failed to change mode', 'error'));
}

/**
 * YouTube Settings
 */
function saveYouTubeKey() {
    const keyInput = document.getElementById('youtube-key-input');
    if (!keyInput) return;
    
    const key = keyInput.value.trim();
    if (!key) {
        showNotification('YouTube key cannot be empty', 'error');
        return;
    }
    
    fetch('/api/settings/youtube-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: key })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok') {
            showNotification('YouTube key saved', 'success');
            keyInput.value = '';
        } else {
            showNotification(`Error: ${data.message}`, 'error');
        }
    })
    .catch(error => showNotification('Failed to save YouTube key', 'error'));
}

function testYouTubeConnection() {
    fetch('/api/stream/health')
        .then(response => response.json())
        .then(data => {
            const status = data.overall_status === 'healthy' ? 'Connected' : 'Not connected';
            showNotification(`YouTube status: ${status}`, 'info');
        })
        .catch(error => showNotification('Connection test failed', 'error'));
}

/**
 * Utility Functions
 */
function updateConnectionStatus(connected) {
    const indicator = document.getElementById('connection-indicator');
    if (indicator) {
        indicator.className = `connection-indicator ${connected ? 'connected' : 'disconnected'}`;
        indicator.textContent = connected ? '● Connected' : '● Disconnected';
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.opacity = '1';
    }, 10);
    
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

/**
 * Fallback polling if WebSocket unavailable
 */
function fallbackToPoll() {
    logger.warn('Falling back to HTTP polling');
    
    setInterval(() => {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => onStatusUpdate(data))
            .catch(error => logger.error(`Poll error: ${error.message}`));
    }, 2000);
}

/**
 * Preview initialization: fetch candidate HLS URLs and attach player
 */
function initPreview() {
    const container = document.getElementById('preview-container');
    if (!container) return;

    fetch('/api/preview')
        .then(r => r.json())
        .then(data => {
            const candidates = data.candidates || [];
            if (candidates.length === 0) {
                container.innerHTML = '<p>No preview available</p>';
                return;
            }

            // Create video element
            const video = document.createElement('video');
            video.id = 'preview-player';
            video.controls = true;
            video.width = 480;
            video.height = 270;
            container.appendChild(video);

            const first = candidates[0];
            if (window.Hls && Hls.isSupported()) {
                const hls = new Hls();
                hls.loadSource(first);
                hls.attachMedia(video);
                hls.on(Hls.Events.MANIFEST_PARSED, function() {
                    // Autoplay muted preview
                    video.muted = true;
                    video.play().catch(() => {});
                });
            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = first;
                video.addEventListener('loadedmetadata', function() {
                    video.muted = true;
                    video.play().catch(() => {});
                });
            } else {
                container.innerHTML = '<p>Preview not supported in this browser</p>';
            }
        })
        .catch(() => {
            if (container) container.innerHTML = '<p>Preview unavailable</p>';
        });
}

/**
 * Simple Logger
 */
const logger = {
    info: (msg) => console.log(`[INFO] ${msg}`),
    warn: (msg) => console.warn(`[WARN] ${msg}`),
    error: (msg) => console.error(`[ERROR] ${msg}`)
};

