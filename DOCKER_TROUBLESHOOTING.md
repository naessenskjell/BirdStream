# BirdStream - Docker Troubleshooting Guide

## Server Docker Issues

### Error: `TypeError: __init__() got an unexpected keyword argument 'static_image_handler'`

**Root Cause:** Parameter name mismatch in `NetworkResilience` initialization.

**Solution:** ✅ FIXED
```python
# WRONG:
network_resilience = NetworkResilience(
    stream_handler=stream_handler,
    youtube_rtmp=youtube_rtmp,
    static_image_handler=static_image_handler  # ← Wrong parameter name
)

# CORRECT:
network_resilience = NetworkResilience(
    stream_handler=stream_handler,
    youtube_rtmp=youtube_rtmp,
    static_images=static_image_handler  # ← Correct parameter name
)
```

**File Updated:** `server/backend/app.py` (line ~47)

**How to Verify:**
```bash
cd server
docker-compose down
docker-compose build
docker-compose up
# Should start without TypeError
```

---

## Raspberry Pi Docker Issues

### Issue 1: `ERROR: picamera2 library not available`

**Root Cause:** Missing build dependencies (gcc, python3-dev, libcap-dev) needed to compile picamera2.

**Solution:** ✅ FIXED - Dockerfile now includes:
```dockerfile
gcc
python3-dev
build-essential
libcap-dev           # ← For camera capabilities
libopenexr-3-1-30    # ← Fixed version (was libopenexr23)
libwebp7             # ← Fixed version (was libwebp6)
```

**File Updated:** `raspberry-pi/Dockerfile` (lines 8-26)

**Requirements.txt Updated:**
```
picamera2>=0.3.0     # ← Lowered from 0.6.0 for compatibility
pyaudio>=0.2.13
pyyaml>=6.0
requests>=2.31.0
numpy>=1.24.0
```

**File Updated:** `raspberry-pi/requirements.txt`

---

## Raspberry Pi Docker Build & Run

### Build the Docker Image

```bash
cd raspberry-pi
docker build -t birdstream-pi:latest .

# Should complete successfully with:
# Successfully tagged birdstream-pi:latest
```

### Run with Proper Camera Access

**For Camera Module (Camera v3 / v2):**

#### Option A: Using libcamera (Recommended for Bullseye+)

```bash
docker run \
  --device /dev/video0 \
  --device /dev/video1 \
  --device /dev/video2 \
  --device /dev/video3 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v /sys/dev/char:/sys/dev/char \
  -v /etc/udev/rules.d:/etc/udev/rules.d:ro \
  --cap-add SYS_ADMIN \
  --cap-add CAP_SYS_RESOURCE \
  birdstream-pi:latest \
  python main.py
```

#### Option B: Using rpicam-vid (Legacy, for older Raspbian)

If you get "picamera2 not available" even with fix:

```bash
# Build custom image that uses rpicam-vid
# First, save your video stream to a named pipe that Python can read:

docker run \
  --privileged \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v /tmp/video_stream:/tmp/video_stream \
  birdstream-pi:latest \
  bash -c "rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o /tmp/video_stream & python main.py"
```

---

## Capability and Device Access

### Why Add These Capabilities?

```dockerfile
--cap-add SYS_ADMIN       # Allows camera subsystem access
--cap-add CAP_SYS_RESOURCE # Allows resource allocation for camera
```

### Video Device Mounting

Raspberry Pi camera typically shows up as:
- `/dev/video0` - H.264 encoder (primary)
- `/dev/video1` - ISP output (alternative)
- `/dev/video2` - Alternative encoder
- `/dev/video3` - Alternative encoder

Mount all to ensure availability:
```bash
--device /dev/video0 \
--device /dev/video1 \
--device /dev/video2 \
--device /dev/video3 \
```

### Verify Camera is Available

```bash
# On Pi host (outside Docker):
ls -la /dev/video*
# Should show: /dev/video0, /dev/video1, etc.

vcgencmd get_camera
# Should show: supported=1 detected=1
```

---

## Audio Device Access

### For USB Microphone (Recommended)

```bash
docker run \
  --device /dev/snd \
  -v /proc/asound:/proc/asound:ro \
  birdstream-pi:latest \
  python main.py
```

### Verify Audio Device

```bash
# On Pi host:
arecord -l
# Should list USB Microphone

# Inside Docker:
docker run --device /dev/snd birdstream-pi:latest arecord -l
```

---

## Docker Run Commands - Quick Reference

### Minimal (Camera only, no audio)
```bash
docker run \
  --device /dev/video0 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  birdstream-pi:latest \
  python main.py
```

### Full (Camera + Audio + Capabilities)
```bash
docker run \
  --device /dev/video0 \
  --device /dev/video1 \
  --device /dev/snd \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v /sys/dev/char:/sys/dev/char \
  --cap-add SYS_ADMIN \
  --cap-add CAP_SYS_RESOURCE \
  -e PYTHONUNBUFFERED=1 \
  birdstream-pi:latest \
  python main.py
```

### With Volume for Persistent Logs
```bash
docker run \
  --device /dev/video0 \
  --device /dev/video1 \
  --device /dev/snd \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v /sys/dev/char:/sys/dev/char \
  --cap-add SYS_ADMIN \
  --cap-add CAP_SYS_RESOURCE \
  -e PYTHONUNBUFFERED=1 \
  --name birdstream-pi \
  birdstream-pi:latest \
  python main.py
```

### Interactive (For Debugging)
```bash
docker run -it \
  --device /dev/video0 \
  --device /dev/snd \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v /sys/dev/char:/sys/dev/char \
  --cap-add SYS_ADMIN \
  --cap-add CAP_SYS_RESOURCE \
  birdstream-pi:latest \
  bash
```

---

## Dockerfile Dependencies Explained

### Build Dependencies (Compile-time)
```dockerfile
gcc                   # C compiler
python3-dev           # Python headers for compilation
build-essential       # Build tools (make, etc.)
```

**Why needed:** picamera2 and some Python packages need to compile C extensions.

### Runtime Dependencies

#### Camera Support
```dockerfile
libcap-dev            # Linux capabilities (camera access)
libjpeg-dev           # JPEG encoding
libopenjp2-7          # JPEG2000 support
libtiff6              # TIFF image support
libwebp7              # WebP image support
libopenexr-3-1-30     # OpenEXR support (image codec)
libharfbuzz0b         # Text rendering
libwebpmux3           # WebP utilities
libopenjp2-tools      # JPEG2000 tools
```

**Why needed:** Camera capture uses multiple image codecs and rendering libraries.

#### Audio Support
```dockerfile
portaudio19-dev       # Audio I/O library
alsa-utils            # Advanced Linux Sound Architecture
```

**Why needed:** PyAudio depends on PortAudio, which uses ALSA on Linux.

#### FFmpeg
```dockerfile
ffmpeg                # Video encoding and streaming
```

**Why needed:** Stream encoder uses FFmpeg for H.264 encoding and RTMP streaming.

---

## Server Docker Build

### Build and Run

```bash
cd server
docker-compose build
docker-compose up -d
```

### Verify Server is Running

```bash
# Check container status
docker-compose ps

# Check logs
docker-compose logs -f birdstream-server

# Test API
curl http://localhost:5000/health
```

### Docker Compose Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f birdstream-server

# Follow only errors
docker-compose logs birdstream-server | grep ERROR
```

---

## Debugging Checklist

### If Server Fails to Start

```bash
# 1. Check logs for error messages
docker-compose logs birdstream-server | tail -20

# 2. Verify port not in use
lsof -i :5000

# 3. Rebuild container
docker-compose down
docker-compose build --no-cache
docker-compose up

# 4. Check Python dependencies
docker-compose run birdstream-server pip list
```

### If Pi Fails to Start

```bash
# 1. Check camera device
docker run --device /dev/video0 birdstream-pi:latest ls -la /dev/video*

# 2. Test picamera2 import
docker run birdstream-pi:latest python -c "from picamera2 import Picamera2; print('OK')"

# 3. Check audio
docker run --device /dev/snd birdstream-pi:latest arecord -l

# 4. Rebuild without cache
docker build --no-cache -t birdstream-pi:latest .
```

### Interactive Debugging

```bash
# Start shell in Pi container
docker run -it \
  --device /dev/video0 \
  --device /dev/snd \
  birdstream-pi:latest \
  bash

# Inside container:
python -c "from picamera2 import Picamera2; Picamera2()"
arecord -l
ffmpeg -version
```

---

## Docker-Compose for Pi

Optional: Use docker-compose for Pi too (for consistency):

**File: `raspberry-pi/docker-compose.yml`**

```yaml
version: '3.8'

services:
  birdstream-pi:
    build: .
    container_name: birdstream-pi
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./logs:/app/logs
    devices:
      - /dev/video0
      - /dev/video1
      - /dev/snd
    cap_add:
      - SYS_ADMIN
      - CAP_SYS_RESOURCE
    privileged: false
    command: python main.py
```

Then run:
```bash
cd raspberry-pi
docker-compose build
docker-compose up -d
docker-compose logs -f
```

---

## Common Docker Issues & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `picamera2 not available` | Missing build deps | ✅ Fixed in Dockerfile |
| `Permission denied` on /dev/video | No device mount | Add `--device /dev/video0` |
| `TypeError: static_image_handler` | Wrong param name | ✅ Fixed in app.py |
| `Port 5000 in use` | Another service on port | `sudo lsof -i :5000` |
| `Cannot connect to server` | Network isolation | Add `--network host` or check DNS |
| `pyaudio import fails` | Missing libsndfile | Dockerfile already has portaudio19-dev |
| `No such file: config.yaml` | Config not mounted | Use `-v $(pwd)/config.yaml:/app/config.yaml` |
| `OSError: [Errno -9996]` | Audio device not mounted | Add `--device /dev/snd` |

---

## Recommended Pi Docker Setup

### Production (Recommended)

```bash
docker run -d \
  --name birdstream-pi \
  --restart unless-stopped \
  --device /dev/video0 \
  --device /dev/video1 \
  --device /dev/snd \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v /sys/dev/char:/sys/dev/char \
  --cap-add SYS_ADMIN \
  --cap-add CAP_SYS_RESOURCE \
  -e PYTHONUNBUFFERED=1 \
  birdstream-pi:latest \
  python main.py
```

### Viewing Logs

```bash
# Real-time
docker logs -f birdstream-pi

# Last 50 lines
docker logs -n 50 birdstream-pi

# Saved to file
docker logs birdstream-pi > /tmp/pi_logs.txt
```

### Stopping/Restarting

```bash
# Stop
docker stop birdstream-pi

# Restart
docker restart birdstream-pi

# Remove (if needed)
docker rm birdstream-pi
```

---

## Testing Checklist

After fixing all issues:

- [ ] Server docker-compose builds without errors
- [ ] Server docker-compose up starts successfully
- [ ] Pi Dockerfile builds without errors
- [ ] Pi docker run starts successfully
- [ ] Camera detected (no "picamera2 not available" warning)
- [ ] Server logs show no TypeError
- [ ] Dashboard loads at `http://server-ip:5000`
- [ ] Pi shows connected on dashboard
- [ ] Video displaying on dashboard (if configured)
- [ ] Metrics updating
- [ ] No errors in logs for 5 minutes

---

## Next Steps

1. **Fix Server:** Update app.py ✅
2. **Fix Pi Dockerfile:** Add dependencies ✅
3. **Rebuild Server:** `docker-compose build && docker-compose up -d`
4. **Rebuild Pi:** `docker build -t birdstream-pi:latest .`
5. **Run Pi:** Use "Recommended Pi Docker Setup" command above
6. **Test:** Follow Testing Checklist
7. **Monitor:** Watch logs and dashboard

Good luck! 🐳
