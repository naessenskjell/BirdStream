# BirdStream - Quick Start Setup Guide

## Prerequisites

### Hardware
- **Raspberry Pi 4+** with 2GB+ RAM
- **Raspberry Pi Camera Module 3 Wide**
- **USB Microphone** (or Pi audio input)
- **Server** running Linux/Docker (Ubuntu 20.04+)
- **WiFi network** (2.4GHz minimum, 5GHz recommended for server)

### Software on Raspberry Pi
- Python 3.9+
- FFmpeg
- Docker & Docker Compose (if using containers)

### Software on Server
- Docker & Docker Compose
- FFmpeg
- Port 5000 available (Flask backend)

---

## Step 1: Clone Repository

### On Raspberry Pi & Server

```bash
git clone https://github.com/naessenskjell/BirdStream.git
cd BirdStream
```

---

## Step 2: Configure Raspberry Pi

### Edit `raspberry-pi/config.yaml`

**Critical Settings:**

```yaml
server:
  host: 192.168.0.21          # ← Change to your SERVER IP
  port: 5000
  reconnect:
    max_retries: 30           # WiFi resilience
  network:
    monitor_enabled: true      # WiFi monitoring
  buffer:
    enabled: true              # Frame buffering
    max_frames: 450

encoder:
  buffer_size: 4194304
  rbuffer_size: 52428800
  sbuffer_size: 52428800
```

**Optional Customization:**

```yaml
camera:
  width: 1920                 # Resolution (1920 = 1080p)
  height: 1080
  fps: 30
  bitrate: 4000               # kbps (4000 = 4 Mbps)

audio:
  sample_rate: 48000
  bitrate: 128                # kbps
```

---

## Step 3: Install Raspberry Pi Dependencies

### Bare Metal (without Docker)

```bash
cd raspberry-pi

# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip ffmpeg alsa-utils libportaudio2

# Install Python packages
pip3 install -r requirements.txt

# Make main.py executable
chmod +x src/main.py
```

### With Docker

```bash
cd raspberry-pi

# Build image
docker build -t birdstream-pi:latest .

# Test run (should exit cleanly)
docker run --device /dev/video0 --device /dev/snd \
  -v $(pwd)/config.yaml:/app/config.yaml \
  birdstream-pi:latest python main.py
```

---

## Step 4: Set Up Server

### Option A: Local Testing (Single Machine)

```bash
cd server

# Install dependencies
pip3 install -r requirements.txt

# Run Flask backend
python3 backend/app.py

# In another terminal, serve frontend:
cd frontend
python3 -m http.server 8000

# Access at: http://localhost:8000
```

### Option B: Docker Deployment (Recommended)

```bash
cd server

# Build images
docker-compose build

# Start services
docker-compose up -d

# Check status
docker-compose ps

# Access at: http://localhost:5000
```

---

## Step 5: Verify Configuration

### Test Raspberry Pi → Server Connection

On Raspberry Pi:

```bash
# Check network connectivity
ping 192.168.0.21    # ← Replace with your server IP

# Check server is running
curl http://192.168.0.21:5000/health
# Expected: {"status": "ok"}

# Check API is accessible
curl http://192.168.0.21:5000/api/status
# Expected: JSON with stream status
```

### Test Camera/Microphone

On Raspberry Pi:

```bash
# Test camera
python3 -c "from picamera2 import Picamera2; Picamera2()" 
# No output = OK

# Test microphone (record 2 seconds)
arecord -d 2 /tmp/test.wav
ls -lh /tmp/test.wav  # Should show ~200KB file
```

---

## Step 6: Start Services

### On Raspberry Pi (Bare Metal)

```bash
cd BirdStream/raspberry-pi
python3 src/main.py

# Expected logs:
# INFO - BirdStream application initialized
# INFO - Configuration loaded from config.yaml
# INFO - CameraCapture initialized: 1920x1080@30fps
# INFO - AudioCapture initialized: USB Microphone
# INFO - Stream Encoder initialized: ffmpeg
# INFO - Successfully connected to server
# INFO - Stream transmission started
```

### On Raspberry Pi (Docker)

```bash
cd BirdStream/raspberry-pi

docker run -d --name birdstream-pi \
  --device /dev/video0 \
  --device /dev/snd \
  -v $(pwd)/config.yaml:/app/config.yaml \
  --restart unless-stopped \
  birdstream-pi:latest

# View logs
docker logs -f birdstream-pi
```

### On Server

```bash
cd BirdStream/server

# If local testing
python3 backend/app.py

# If Docker
docker-compose up -d

# Check services running
ps aux | grep "python\|docker"
# Or: docker-compose ps
```

---

## Step 7: Access Dashboard

### Open Web Browser

```
http://192.168.0.21:5000
```

**Dashboard Tabs:**
- **Status** - Stream state, controls
- **Metrics** - Bitrate, frame count, graphs
- **Logs** - Event logs
- **Settings** - YouTube key, preferences
- **Images** - Fallback image upload

---

## Step 8: Configure YouTube Streaming (Optional)

### Get YouTube Stream Key

1. Go to YouTube Studio → Go Live
2. Copy RTMP URL: `rtmp://a.rtmp.youtube.com/live2/XXXXXXXXXXXXXX`
3. Extract key: `XXXXXXXXXXXXXX`

### Add to Dashboard

1. Open dashboard → Settings tab
2. Paste YouTube stream key
3. Click [Save Key]
4. Click [Test Connection]
5. Expected: "Connected successfully"

### Start Streaming

1. Go to Status tab
2. Click [▶ Stream to YouTube]
3. Check YouTube Live tab (should show stream after 30 seconds)

---

## Step 9: Upload Fallback Image (Optional)

### Why
If WiFi fails, stream automatically switches to static image (prevents YouTube from going offline)

### How

1. Open dashboard → Images tab
2. Click [☁️ Upload Image]
3. Select JPG/PNG (max 10MB)
4. Wait for confirmation
5. Click [Select] to make it active

---

## Troubleshooting

### Raspberry Pi Won't Start

```bash
# Check Python version
python3 --version     # Should be 3.9+

# Check dependencies
pip3 list | grep picamera2
# Should see: picamera2

# Test import
python3 -c "from picamera2 import Picamera2; print('OK')"

# Check camera
ls -la /dev/video0
# Should exist
```

### Can't Connect to Server

```bash
# From Raspberry Pi:
ping 192.168.0.21
curl http://192.168.0.21:5000/health

# Check firewall on server
sudo ufw status
sudo ufw allow 5000/tcp

# Check if Flask running
ps aux | grep python
curl http://localhost:5000/health
```

### No Audio/Video

```bash
# Check camera
vcgencmd get_camera
# Should output: supported=1 detected=1

# List audio devices
arecord -l
# Should show USB microphone

# Test capture directly
python3 src/camera_capture.py
python3 src/audio_capture.py
```

### WiFi Keeps Disconnecting

Increase buffer and retry settings in `config.yaml`:

```yaml
server:
  reconnect:
    max_retries: 60          # 20+ minutes
    backoff_multiplier: 1.2  # Gentler scaling
    initial_delay: 1
    max_delay: 45
```

### Server Dashboard Not Loading

```bash
# Check Flask running
curl http://localhost:5000/api/status

# Check logs
tail -f /var/log/birdstream.log

# Restart Flask
# Ctrl+C to stop
python3 backend/app.py
```

---

## File Locations

| What | Where | Notes |
|------|-------|-------|
| **Config** | `raspberry-pi/config.yaml` | Edit: server IP, bitrate, WiFi settings |
| **Camera Code** | `raspberry-pi/src/camera_capture.py` | Phase 2 implementation |
| **Audio Code** | `raspberry-pi/src/audio_capture.py` | Phase 2 implementation |
| **Encoder** | `raspberry-pi/src/stream_encoder.py` | Phase 2 implementation |
| **Network** | `raspberry-pi/src/network_stream.py` | WiFi resilience code |
| **Main** | `raspberry-pi/src/main.py` | Entry point |
| **Server** | `server/backend/app.py` | Flask API |
| **Frontend** | `server/frontend/index.html` | Dashboard UI |
| **Logs (Pi)** | `/var/log/birdstream.log` | Check for errors |
| **Logs (Server)** | `server/logs/` | Check for errors |
| **Images** | `server/images/` | Uploaded fallback images |

---

## Key Configuration Parameters

### WiFi Resilience (Critical for Stability)

```yaml
server:
  network:
    monitor_enabled: true     # Enable WiFi monitoring
    check_interval: 5         # Check every 5 seconds
  buffer:
    enabled: true             # Buffer frames during outage
    max_frames: 450           # ~15 seconds at 30fps
```

### Streaming Quality

```yaml
camera:
  bitrate: 4000               # Kbps (lower = smaller, more stable)
                              # Adjust down if WiFi unstable
  fps: 30                     # Frames per second
  width: 1920
  height: 1080

audio:
  bitrate: 128                # Kbps (usually fine, don't change)
```

### Server Connection

```yaml
server:
  host: 192.168.0.21          # Your server IP (CRITICAL!)
  port: 5000                  # Flask port
  timeout: 10                 # Connection timeout in seconds
```

---

## Quick Commands

### Check Everything Running

```bash
# On Raspberry Pi
curl http://192.168.0.21:5000/api/status | jq .

# Network status
curl http://192.168.0.21:5000/api/status/network | jq .

# Logs
tail -f /var/log/birdstream.log
```

### Stop Everything

```bash
# On Raspberry Pi
Ctrl+C

# On Server
Ctrl+C
# Or: docker-compose down
```

### Restart Everything

```bash
# Raspberry Pi
python3 src/main.py

# Server
python3 backend/app.py
# Or: docker-compose restart
```

---

## Performance Expectations

### Network Usage
- Video: 4000 kbps (~500 KB/s)
- Audio: 128 kbps (~16 KB/s)
- Total: ~2 GB per hour

### CPU Usage
- **Raspberry Pi:** 30-50% (H.264 hardware accelerated)
- **Server:** <10% (just proxying)

### Latency
- **WiFi → Server:** 50-500ms (depending on network)
- **Server → YouTube:** 2-5 seconds (YouTube default)

---

## Next Steps

After setup is working:

1. **Test WiFi Resilience** - Disconnect WiFi for 1-2 minutes
   - Watch logs for buffering
   - Check buffer fills up
   - Verify recovery on reconnection

2. **Fine-tune Bitrate** - If unstable, reduce bitrate:
   ```yaml
   camera:
     bitrate: 2500  # Lower = more stable
   ```

3. **Configure YouTube** - Add stream key for live broadcasting

4. **Deploy to Production** - Use Docker for reliability:
   ```bash
   docker-compose up -d --restart unless-stopped
   ```

5. **Monitor Logs** - Check for errors:
   ```bash
   tail -f /var/log/birdstream.log | grep -E "ERROR|WiFi|Buffer"
   ```

---

## Support

### Documentation
- **Detailed WiFi Guide:** `WIFI_RESILIENCE.md`
- **Architecture:** `WIFI_ARCHITECTURE.md`
- **API Reference:** Check `/api/` endpoints in Flask
- **Full Setup:** `SETUP.md`

### Common Issues
1. **Can't connect to server** - Check server IP in config.yaml
2. **WiFi disconnects** - Increase max_retries and buffer_size
3. **No video/audio** - Check camera/microphone detection
4. **Dashboard not loading** - Check Flask is running

---

## Checklist

- [ ] Clone repository
- [ ] Edit `config.yaml` with server IP
- [ ] Install dependencies (Pi)
- [ ] Install dependencies (Server)
- [ ] Start server
- [ ] Start Raspberry Pi
- [ ] Access dashboard at http://server-ip:5000
- [ ] Check "Status" tab shows LIVE
- [ ] (Optional) Configure YouTube key
- [ ] (Optional) Upload fallback image
- [ ] Test WiFi outage (simulated)
- [ ] Verify recovery and frame buffering

---

**You're ready to go!** 🚀
