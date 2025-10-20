# Implementation Plan - BirdStream Project

## 1. Project Overview

**Goal:** Build a robust streaming system that transmits video and audio from a Raspberry Pi to a server, with the capability to stream to YouTube or static images.

**Hardware:**
- Raspberry Pi 3 B+ (192.168.0.22) with Camera Module 3 Wide + Mono USB Microphone
- Ubuntu Server with Docker (192.168.0.21)
- WiFi 2.4 GHz connection (unreliable)

---

## 2. Architecture Overview

```
┌─────────────────────┐
│   Raspberry Pi      │
│  - Camera capture   │
│  - Audio capture    │
│  - Stream encoding  │
│  (1080p 30fps)      │
└──────────┬──────────┘
           │ WiFi
           │ (RTMP/Custom)
           ▼
┌─────────────────────┐
│  Server (Docker)    │
│  - Receive stream   │
│  - Web Interface    │
│  - Route output:    │
│    * YouTube RTMP   │
│    * Static images  │
│    * OFF            │
└─────────────────────┘
```

---

## 3. Phase 1: Preparation & Setup

### 3.1 Repository Structure
```
BirdStream/
├── raspberry-pi/
│   ├── src/
│   │   ├── camera_capture.py
│   │   ├── audio_capture.py
│   │   ├── stream_encoder.py
│   │   └── network_stream.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── config.yaml
├── server/
│   ├── backend/
│   │   ├── app.py
│   │   ├── stream_handler.py
│   │   ├── youtube_rtmp.py
│   │   ├── static_image_handler.py
│   │   ├── network_resilience.py
│   │   ├── settings_manager.py
│   │   └── logger.py
│   ├── frontend/
│   │   ├── index.html
│   │   ├── style.css
│   │   └── app.js
│   ├── images/
│   │   └── (uploaded static images)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── docker-compose.yml
├── docs/
│   ├── SETUP.md
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── TROUBLESHOOTING.md
└── tests/
    ├── test_stream_capture.py
    └── test_server_api.py
```

### 3.2 Dependency Analysis

**Raspberry Pi:**
- Python 3.9+
- picamera2 (Camera capture)
- pyaudio (Audio capture)
- ffmpeg (Encoding)
- requests (HTTP calls)
- pyyaml (Configuration)

**Server:**
- Python 3.9+ (Flask/FastAPI)
- ffmpeg (Stream processing)
- Docker & Docker Compose
- JavaScript frontend (Vanilla JS or Vue.js)

---

## 4. Phase 2: Raspberry Pi - Capture Layer

### 4.1 Camera Capture (`camera_capture.py`)
**Task:** Video capture from Camera Module 3 Wide
- Output format: 1080p 30fps
- Codec: H.264
- Buffer management for WiFi drops
- Error handling & retry logic

**Deliverable:** Python module with camera stream output

### 4.2 Audio Capture (`audio_capture.py`)
**Task:** Audio capturing from USB Microphone
- Format: 48kHz, 16-bit mono
- Sync with video stream
- Low-latency processing
- USB device detection

**Deliverable:** Python module with audio stream output

### 4.3 Stream Encoder (`stream_encoder.py`)
**Task:** Combine video/audio + encoding
- Input: Video stream + Audio stream
- Output: RTMP stream or custom protocol
- Bitrate optimization
- Real-time encoding

**Deliverable:** Encoder module that merges video/audio

### 4.4 Network Stream (`network_stream.py`)
**Task:** Stream to server over network
- Protocol: RTMP or custom UDP/TCP
- Connection resilience
- Automatic reconnection
- Buffer management

**Deliverable:** Network client module

---

## 5. Phase 3: Server - Reception & Processing

### 5.1 Stream Receiver (`stream_handler.py`)
**Task:** Receive incoming stream
- RTMP listener or custom socket
- Stream parsing
- Buffer management
- Connection monitoring

**Deliverable:** Stream reception service

### 5.2 Output Routing Engine
**Module A: YouTube RTMP (`youtube_rtmp.py`)**
- YouTube Stream Key management
- RTMP protocol handling
- Output: Live stream to YouTube in 1080p 30fps
- Audio sync verification

**Module B: Static Image Handler (`static_image_handler.py`)**
- Image upload/storage
- Image serving in 1080p
- Silent audio generation
- Image rotation/update

**Module C: Off State**
- Graceful stream termination
- Resource cleanup

**Deliverable:** 3 routing modules

### 5.3 Network Resilience & Stream Recovery (`network_resilience.py`)
**Task:** Handle WiFi drops and stream recovery
- Connection monitoring (video, audio, or both)
- Automatic buffering during drops
- Automatic fallback to 'reconnecting' state
- Reconnection strategy with exponential backoff
- Stream state tracking (connected, reconnecting, failed)
- Statistics tracking
- Graceful degradation if only one stream is lost

**Deliverable:** Resilience module with reconnecting state management

### 5.4 Settings Manager (`settings_manager.py`)
**Task:** Manage configuration
- YouTube stream key storage (secured)
- Stream settings (bitrate, quality)
- Image upload limits
- Persistent storage (JSON/database)

**Deliverable:** Settings management API

### 5.5 Logging System
**Deliverable:** 
- Structured logging on Pi & Server
- Performance metrics
- Error tracking
- Connection statistics

---

## 6. Phase 4: Web Interface

### 6.1 Backend API (Flask/FastAPI)
**Endpoints:**

| Method | Endpoint | Function |
|--------|----------|----------|
| GET | `/api/status` | Current state (live/static/off/reconnecting) + connection details |
| GET | `/api/stream/health` | Stream health (video OK, audio OK, both OK, reconnecting) |
| GET | `/api/logs` | Recent logs |
| POST | `/api/mode` | Switch mode (live/static/off) |
| POST | `/api/settings/youtube-key` | Update YouTube key |
| POST | `/api/images/upload` | Upload static image |
| GET | `/api/images/list` | List available images |
| DELETE | `/api/images/<id>` | Delete image |
| GET | `/api/metrics` | Performance metrics and stream stats |

**Deliverable:** RESTful API

### 6.2 Frontend UI
**Features:**
- Mode selector (Live / Static Image / Off)
- Status indicator with detailed connection state (Live / Reconnecting / Offline / Static / Off)
- Stream health indicator (Video + Audio status)
- Automatic fallback notification when reconnecting
- Static image selector + upload
- Settings panel (YouTube key, etc.)
- Live metrics display including recovery statistics
- Log viewer with connection event history
- Real-time notification of stream state changes

**Tech:** HTML5 + CSS3 + Vanilla JavaScript

**Deliverable:** Responsive web interface with reconnecting state visibility

---

## 7. Phase 5: Docker Containerization

### 7.1 Raspberry Pi Dockerfile
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ .
CMD ["python", "main.py"]
```

### 7.2 Server Dockerfile
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y ffmpeg
RUN pip install -r requirements.txt
COPY backend/ .
COPY frontend/ ./static/
CMD ["python", "app.py"]
```

### 7.3 Docker Compose (Server)
- Service 1: Stream receiver & processor
- Service 2: Web API backend
- Networking: bridge network
- Volumes: persistent image storage

**Deliverable:** Production-ready Docker setup

---

## 8. Phase 6: Optimization & Performance

### 8.1 Server-side Optimization
- Lightweight Python libraries (no heavy ML frameworks)
- Efficient buffer management
- CPU usage monitoring
- Memory optimization

### 8.2 Network Optimization
- Adaptive bitrate
- Smart buffering
- Compression tuning

**Deliverable:** Performance optimized system

---

## 9. Phase 7: Documentation & Testing

### 9.1 Documentation
**Files:**
- `SETUP.md` - Installation & configuration
- `ARCHITECTURE.md` - System design overview
- `API.md` - API reference
- `TROUBLESHOOTING.md` - Common issues
- Inline code comments

### 9.2 Testing Strategy
- Unit tests (capture, encoding, API)
- Integration tests (end-to-end stream)
- Network simulation tests
- Load tests

**Deliverable:** Comprehensive documentation + test suite

---

## 10. Implementation Timeline

| Phase | Component | Priority | Duration | Dependencies |
|-------|-----------|----------|----------|--------------|
| 1 | Repository setup | HIGH | 1 day | None |
| 2.1 | Camera capture | HIGH | 2 days | Pi setup |
| 2.2 | Audio capture | HIGH | 2 days | Pi setup |
| 2.3 | Stream encoder | HIGH | 3 days | 2.1, 2.2 |
| 2.4 | Network stream | HIGH | 2 days | 2.3 |
| 3.1 | Stream receiver | HIGH | 2 days | 2.4 |
| 3.2 | Output routing | HIGH | 4 days | 3.1 |
| 3.3 | Network resilience | MEDIUM | 2 days | 3.1 |
| 3.4 | Settings manager | MEDIUM | 1 day | 3.2 |
| 3.5 | Logging system | MEDIUM | 1 day | All |
| 4 | Web interface | MEDIUM | 3 days | 3.1-3.4 |
| 5 | Docker setup | MEDIUM | 2 days | All modules |
| 6 | Optimization | LOW | 2 days | 5 |
| 7 | Documentation & Tests | MEDIUM | 3 days | All |

**Estimated total duration: 4-5 weeks**

---

## 11. Risk Analysis & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| WiFi drops | HIGH | Buffer implementation, auto-reconnect |
| Audio sync issues | HIGH | Timestamp-based sync, PTS correction |
| Server performance | MEDIUM | Efficient codecs, monitoring, optimization |
| Latency | MEDIUM | Direct RTMP streaming, buffer tuning |
| Configuration management | LOW | Web UI for settings, persistent storage |

---

## 12. Success Criteria

- ✅ Video 1080p 30fps to YouTube without drops
- ✅ Audio sync within 100ms
- ✅ WiFi drops not visible in output (seamless buffering)
- ✅ Web interface responsive & accessible
- ✅ Server automatically detects stream loss (video/audio/both)
- ✅ Server automatically enters 'reconnecting' state on stream loss
- ✅ Server attempts recovery without manual intervention
- ✅ System recovery < 5 seconds
- ✅ Reconnecting state clearly visible in web UI
- ✅ Server CPU < 50% under normal load
- ✅ Complete documentation
- ✅ Docker containers production-ready

---

## 13. Next Steps

1. **Setup repository** with folder structure
2. **Install dependencies** on Pi and Server
3. **Start with Phase 2.1** - Camera capture proof of concept
4. **Iterative development** with testing
5. **Integration testing** between Pi and Server
6. **Performance tuning** and optimization
7. **Final documentation** and deployment

