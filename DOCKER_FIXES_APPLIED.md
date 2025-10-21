# Docker Fixes - Summary

## ✅ Fixed Issues

### 1. Server TypeError (FIXED)

**Error:**
```
TypeError: __init__() got an unexpected keyword argument 'static_image_handler'
```

**File:** `server/backend/app.py` line ~47

**Change:**
```python
# BEFORE:
network_resilience = NetworkResilience(
    stream_handler=stream_handler,
    youtube_rtmp=youtube_rtmp,
    static_image_handler=static_image_handler  # ← WRONG
)

# AFTER:
network_resilience = NetworkResilience(
    stream_handler=stream_handler,
    youtube_rtmp=youtube_rtmp,
    static_images=static_image_handler  # ← CORRECT
)
```

**Status:** ✅ Applied

---

### 2. Pi Dockerfile Missing Dependencies (FIXED)

**Error:**
```
WARNING:root:picamera2 not available - running in simulation mode
ERROR:camera_capture:picamera2 library not available
```

**File:** `raspberry-pi/Dockerfile` lines 8-26

**Added Dependencies:**
```dockerfile
gcc              # C compiler for compilation
python3-dev      # Python headers
build-essential  # Build tools
libcap-dev       # Camera capabilities (CRITICAL)
libopenexr-3-1-30  # Fixed version (was 23)
libwebp7         # Fixed version (was 6)
```

**Status:** ✅ Applied

---

### 3. Requirements.txt Version (UPDATED)

**File:** `raspberry-pi/requirements.txt`

**Change:**
```
picamera2>=0.3.0  # Lowered from 0.6.0 for broader compatibility
```

**Status:** ✅ Applied

---

## 🚀 Next Steps

### Step 1: Rebuild Server

```bash
cd server
docker-compose build
docker-compose down
docker-compose up
```

**Expected Result:** Server starts without TypeError ✅

### Step 2: Rebuild Pi Docker Image

```bash
cd raspberry-pi
docker build -t birdstream-pi:latest .
```

**Expected Result:** Build completes successfully without errors ✅

### Step 3: Run Pi Container

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

**Expected Result:**
- picamera2 initializes successfully
- No "not available" warnings
- Stream connects to server
- Dashboard shows LIVE status

---

## 📋 Important Notes

### Camera Device Mounting

Your reference command was:
```bash
rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o -
```

This indicates your Pi has **libcamera** support (Bullseye or newer). The fixed Dockerfile now supports this:

1. **Build dependencies** (gcc, build-essential) let picamera2 compile against libcamera
2. **libcap-dev** gives proper capabilities for camera access
3. **Video device mounting** (`--device /dev/video0`, etc.) provides access

### Why We Mount Multiple Video Devices

```bash
--device /dev/video0   # H.264 encoder
--device /dev/video1   # ISP output
--device /dev/video2   # Alternative encoder
--device /dev/video3   # Alternative encoder
```

picamera2 may use any of these. Mounting all ensures availability.

### Security vs Functionality Trade-off

```bash
--cap-add SYS_ADMIN          # Allows camera subsystem access
--cap-add CAP_SYS_RESOURCE   # Allows resource allocation
--privileged                 # Can remove this; above caps are usually enough
```

Using specific capabilities is more secure than `--privileged`.

---

## 📄 Documentation

Full troubleshooting guide created: **DOCKER_TROUBLESHOOTING.md**

Includes:
- Detailed explanations for each fix
- Complete docker run commands
- Debugging checklist
- Common issues & solutions
- Docker-compose for Pi (optional)
- Testing checklist

---

## 🧪 Quick Verification

After applying fixes:

### Server
```bash
# In server directory
docker-compose build 2>&1 | grep -i error
# Should show: nothing

docker-compose up 2>&1 | grep TypeError
# Should show: nothing
```

### Pi
```bash
# In raspberry-pi directory
docker build -t birdstream-pi:latest . 2>&1 | grep -i error
# Should show: nothing

docker run birdstream-pi:latest python -c "from picamera2 import Picamera2; print('OK')"
# Should print: OK
```

---

**All fixes applied ✅**

Ready to rebuild and test!
