# Phase 3 Quick Reference

## 🎯 Phase 3 Objectives - ALL COMPLETE ✅

- [x] Create stream_handler.py (RTMP reception)
- [x] Create youtube_rtmp.py (YouTube routing)
- [x] Create static_image_handler.py (Image fallback)
- [x] Create network_resilience.py (State machine)
- [x] Create settings_manager.py (Configuration)
- [x] Create logger.py (Logging/metrics)
- [x] Integrate all modules into app.py

## 📦 Module Cheat Sheet

### stream_handler.py
```python
from stream_handler import StreamHandler

handler = StreamHandler()
handler.register_connection('pi-001')
handler.receive_video('pi-001', frame_data)
handler.receive_audio('pi-001', audio_data)
stream_info = handler.get_active_streams()
```

### youtube_rtmp.py
```python
from youtube_rtmp import YouTubeRTMP

youtube = YouTubeRTMP()
youtube.set_stream_key('your-stream-key')
youtube.start()  # Start FFmpeg encoder
youtube.stop()   # Stop encoder
status = youtube.get_status()
```

### static_image_handler.py
```python
from static_image_handler import StaticImageHandler

images = StaticImageHandler()
image_id = images.upload_image(file_obj)
images.delete_image(image_id)
images.select_image(image_id)
images.start_streaming()  # Fallback to image
images.stop_streaming()
list_images = images.list_images()
```

### network_resilience.py
```python
from network_resilience import NetworkResilience, StreamState

resilience = NetworkResilience(stream_handler, youtube_rtmp, images)
resilience.on_state_changed = callback_func
resilience.start_monitoring()  # Start state machine
resilience.handle_video_loss()  # Trigger recovery
resilience.handle_audio_loss()
resilience.stop()

# States: OFF, LIVE, RECONNECTING, STATIC, ERROR
current = resilience.current_state  # Returns StreamState
```

### settings_manager.py
```python
from settings_manager import SettingsManager

config = SettingsManager()
config.set('youtube_stream_key', 'key-here')
key = config.get('youtube_stream_key')
config.save()  # Persists to settings.json
all_settings = config.get_all()  # Excludes sensitive data
```

### logger.py
```python
from logger import StreamLogger, MetricsCollector, ConnectionStatistics

# Logging
logger = StreamLogger()
logger.log_event('INFO', 'stream', 'Stream started', {'bitrate': 4000})
logs = logger.get_recent_logs(count=50, event_type='error')

# Metrics
metrics = MetricsCollector()
metrics.record_video_frame(1024)
metrics.record_audio_frame(512)
metrics.record_video_error()
data = metrics.get_metrics()

# Connection Stats
stats = ConnectionStatistics()
stats.record_new_connection()
stats.record_recovery_attempt()
conn_stats = stats.get_stats()
```

## 🔌 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/status | GET | Stream state and health |
| /api/stream/health | GET | Detailed metrics |
| /api/logs | GET | Recent log entries |
| /api/mode | POST | Set stream mode |
| /api/settings/youtube-key | POST | Update YouTube key |
| /api/images/upload | POST | Upload fallback image |
| /api/images/list | GET | List images |
| /api/images/<id> | DELETE | Delete image |
| /api/metrics | GET | Performance metrics |

## 🔄 State Machine States

```
OFF ─→ LIVE ─→ RECONNECTING ─→ STATIC ─→ ERROR
 ↑                                   ↓
 └───────────────────────────────────┘
```

- **OFF**: No streaming
- **LIVE**: Active YouTube stream
- **RECONNECTING**: Attempting recovery (exp. backoff, 10 attempts)
- **STATIC**: Fallback image (1fps loop)
- **ERROR**: Unrecoverable failure

## ⏱️ Recovery Timing

- Wait 1s → Retry 1
- Wait 2s → Retry 2
- Wait 4s → Retry 3
- Wait 8s → Retry 4
- Wait 16s → Retry 5
- Wait 60s → Retries 6-10
- **Total:** ~5.5 minutes to fallback

## 📊 Settings (settings.json)

```json
{
  "youtube_stream_key": "",           // Set via API
  "youtube_enabled": true,            // Enable YouTube
  "static_image_fallback": true,      // Enable fallback
  "auto_recover": true,               // Auto-recovery on loss
  "recovery_timeout": 30,             // Timeout before loss detected
  "max_recovery_attempts": 10,        // Max reconnect attempts
  "stream_bitrate": 4000,             // kbps to YouTube
  "stream_fps": 30,                   // FPS to YouTube
  "image_upload_limit": 104857600     // 100MB
}
```

## 🗂️ Directory Structure

```
server/backend/
├── app.py                      # Flask app (337 lines)
├── stream_handler.py           # RTMP receiver (350 lines)
├── youtube_rtmp.py             # YouTube encoder (280 lines)
├── static_image_handler.py     # Image fallback (300 lines)
├── network_resilience.py       # State machine (350 lines)
├── settings_manager.py         # Config (250 lines)
├── logger.py                   # Logging (250 lines)
├── settings.json               # Persisted config
├── logs/
│   └── birdstream.log          # Rotating log file
├── images/                     # Uploaded fallback images
├── static/                     # Web UI assets
└── templates/                  # Flask templates
```

## 🚀 Startup Sequence

```python
# app.py startup
if __name__ == '__main__':
    # 1. Initialize modules
    stream_handler = StreamHandler()
    youtube_rtmp = YouTubeRTMP()
    static_image_handler = StaticImageHandler()
    network_resilience = NetworkResilience(...)
    settings_manager = SettingsManager()
    stream_logger = StreamLogger()
    
    # 2. Load persisted settings
    youtube_key = settings_manager.get('youtube_stream_key')
    if youtube_key:
        youtube_rtmp.set_stream_key(youtube_key)
    
    # 3. Register callbacks
    network_resilience.on_state_changed = on_stream_state_changed
    
    # 4. Start monitoring
    network_resilience.start_monitoring()
    
    # 5. Run Flask server
    app.run(host='0.0.0.0', port=5000)
```

## 🔧 Common Tasks

### Start streaming to YouTube
```bash
curl -X POST http://server:5000/api/settings/youtube-key \
  -H "Content-Type: application/json" \
  -d '{"key":"your-youtube-rtmp-key"}'

curl -X POST http://server:5000/api/mode \
  -H "Content-Type: application/json" \
  -d '{"mode":"live"}'
```

### Check stream health
```bash
curl http://server:5000/api/stream/health
```

### Upload fallback image
```bash
curl -F "image=@image.jpg" \
  http://server:5000/api/images/upload
```

### Get recent logs
```bash
curl "http://server:5000/api/logs?count=20&type=error"
```

### Get performance metrics
```bash
curl http://server:5000/api/metrics
```

## 🐛 Troubleshooting

### Import errors
- Ensure all Phase 3 modules are in `/server/backend/`
- Check Python path includes backend directory

### YouTube key not persisting
- Check `settings.json` exists in backend directory
- Verify write permissions in backend folder

### Static image fallback not working
- Upload image via `/api/images/upload`
- Check `images/` directory exists
- Verify FFmpeg installed on system

### Stream keeps reconnecting
- Check video/audio data flowing from Raspberry Pi
- Verify network connectivity between Pi and Server
- Check recovery timeout (default 30s)

### High memory usage
- Check log rotation (max 10MB per file)
- Check image size (upload limit 10MB per image)
- Monitor metrics with `/api/metrics`

## ✅ Verification

After setup, test with:

```bash
# 1. Server health
curl http://localhost:5000/health

# 2. API status
curl http://localhost:5000/api/status

# 3. Stream health
curl http://localhost:5000/api/stream/health

# 4. Metrics
curl http://localhost:5000/api/metrics

# 5. Logs
curl http://localhost:5000/api/logs
```

Expected response format:
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "stream_state": "off",
  "video_ok": false,
  "audio_ok": false
}
```

## 📝 Next Phase

**Phase 4: Web Interface Enhancement**
- Real-time dashboard
- Stream preview
- Bandwidth monitoring
- Recovery progress tracking

---

**Last Updated:** Phase 3 Complete  
**Lines of Code:** 2,187  
**Modules:** 7  
**API Endpoints:** 9 (fully implemented)
