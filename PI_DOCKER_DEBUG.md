# BirdStream - Pi Docker Debug Guide

## Problem: picamera2 Import Fails in Docker

**Symptoms:**
```
WARNING:root:picamera2 not available - running in simulation mode
ERROR:camera_capture:picamera2 library not available
ERROR:__main__:Failed to initialize camera
```

---

## Step 1: Debug Inside Container

### Interactive Shell

```bash
docker run -it \
  --device /dev/video0 \
  --device /dev/video1 \
  --device /dev/snd \
  birdstream-pi:latest \
  bash
```

### Inside container, test each dependency:

```bash
# Test 1: Is picamera2 installed?
python3 -m pip list | grep picamera2
# Should show: picamera2 0.3.x or higher

# Test 2: Can we import it?
python3 -c "from picamera2 import Picamera2; print('SUCCESS')"
# If this fails, see "ImportError Solutions" below

# Test 3: Check for missing compile dependencies
python3 -c "import picamera2; print(picamera2.__file__)"
# Should show path like /usr/local/lib/python3.9/site-packages/picamera2/

# Test 4: Check libcamera
python3 -c "from libcamera import controls; print('libcamera OK')"

# Test 5: List what's installed
pip list | grep -E "picamera|libcamera|numpy|pyyaml"
```

---

## Step 2: If picamera2 Import Fails

### Option A: Reinstall with Verbose Output

Inside the container:

```bash
pip install --no-cache-dir --force-reinstall -v picamera2>=0.3.0
# Watch for errors in the output
```

If that fails, check for compilation errors:

```bash
pip install --no-cache-dir --force-reinstall -v picamera2 2>&1 | grep -A5 "error:"
```

### Option B: Check for Missing Build Dependencies

```bash
# Verify build tools are present
which gcc
which python3-config
ls /usr/include/python3.9/

# If any are missing, the container image needs fixing
```

---

## Step 3: Rebuild Docker Image with Debugging

### Add verbose output to Dockerfile

Create `Dockerfile.debug`:

```dockerfile
# Raspberry Pi Dockerfile - Debug Version
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for picamera2, pyaudio, and ffmpeg
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    build-essential \
    ffmpeg \
    libjpeg-dev \
    libssl-dev \
    libffi-dev \
    libopenjp2-7 \
    libtiff6 \
    libwebp7 \
    libopenexr-3-1-30 \
    libharfbuzz0b \
    libwebpmux3 \
    libopenjp2-tools \
    libcap-dev \
    portaudio19-dev \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .

# Install with verbose output
RUN pip install --no-cache-dir -v -r requirements.txt 2>&1 | tee /app/pip_install.log

# Verify installation
RUN python3 -c "from picamera2 import Picamera2; print('✓ picamera2 OK')" && \
    python3 -c "import pyaudio; print('✓ pyaudio OK')" && \
    python3 -c "import yaml; print('✓ yaml OK')"

# Copy application source code
COPY src/ .

# Create config directory
RUN mkdir -p /config

# Run the main application
CMD ["python", "main.py"]
```

Build with debug:

```bash
docker build -f Dockerfile.debug -t birdstream-pi:debug .
```

Check logs:

```bash
docker run birdstream-pi:debug cat /app/pip_install.log
```

---

## Step 4: Check If This is a Bullseye vs Bookworm Issue

Your reference command used `rpicam-vid`, which suggests **libcamera-based** Raspberry Pi OS.

### On the Pi host (NOT in Docker):

```bash
lsb_release -d
# If it shows "Bullseye" or "Bookworm", that matters

cat /etc/os-release | grep VERSION_CODENAME
# Shows: bullseye or bookworm
```

### If Bookworm (newer):

The Python 3.9 base image might be too old. Try Python 3.11:

Update `Dockerfile`:

```dockerfile
FROM python:3.11-slim  # Changed from 3.9-slim
```

picamera2 works better on newer Python versions with Bookworm.

---

## Step 5: Verify Camera Access Inside Container

Even if picamera2 imports, the camera might not be accessible:

```bash
# Inside container, check device access
ls -la /dev/video*
# Should show: /dev/video0, /dev/video1, etc.

# Check if we can read from camera
cat /dev/video0 > /tmp/test.raw 2>&1
# If this shows "permission denied", camera access isn't working
```

If camera access fails, ensure you're using the correct docker run flags:

```bash
docker run \
  --device /dev/video0 \
  --device /dev/video1 \
  --device /dev/video2 \
  --device /dev/video3 \
  --device /dev/snd \
  -v /sys/dev/char:/sys/dev/char \
  --cap-add SYS_ADMIN \
  --cap-add CAP_SYS_RESOURCE \
  birdstream-pi:latest \
  python main.py
```

---

## Step 6: Alternative - Use Alternative Dockerfile

If picamera2 continues to fail, try a Raspberry Pi OS-based image instead of Debian slim:

Create `Dockerfile.rpi`:

```dockerfile
# Use official Raspberry Pi OS image
FROM balena/rpi-raspbian:bullseye

RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    build-essential \
    ffmpeg \
    gcc \
    libcap-dev \
    portaudio19-dev \
    alsa-utils

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY src/ .
RUN mkdir -p /config

CMD ["python3", "main.py"]
```

Build:
```bash
docker build -f Dockerfile.rpi -t birdstream-pi:rpi .
```

---

## Step 7: Fallback - Use rpicam-vid Approach

If Docker with picamera2 keeps failing, use rpicam-vid directly:

Create wrapper script `src/camera_fallback.py`:

```python
"""Fallback camera using rpicam-vid"""
import subprocess
import logging

logger = logging.getLogger(__name__)

def capture_with_rpicam():
    """Use rpicam-vid if picamera2 fails"""
    cmd = [
        'rpicam-vid',
        '-t', '0',           # Run forever
        '--inline',          # Output to stdout
        '--width', '1920',
        '--height', '1080',
        '--framerate', '30',
        '-o', '-'
    ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("rpicam-vid streaming started")
        return process
    except FileNotFoundError:
        logger.error("rpicam-vid not found")
        return None
```

Then modify `camera_capture.py`:

```python
try:
    from picamera2 import Picamera2
    from libcamera import controls
except ImportError:
    logging.warning("picamera2 not available - trying rpicam-vid fallback")
    from camera_fallback import capture_with_rpicam
    Picamera2 = None
```

---

## Debugging Checklist

Run through these in order:

```bash
# 1. Check Python version in container
docker run birdstream-pi:latest python3 --version

# 2. Check if picamera2 is installed
docker run birdstream-pi:latest pip list | grep picamera

# 3. Try to import picamera2
docker run birdstream-pi:latest python3 -c "from picamera2 import Picamera2"

# 4. Try to import libcamera
docker run birdstream-pi:latest python3 -c "from libcamera import controls"

# 5. Check if video devices exist in container
docker run --device /dev/video0 birdstream-pi:latest ls -la /dev/video*

# 6. Try to instantiate camera
docker run --device /dev/video0 --device /dev/video1 birdstream-pi:latest \
    python3 -c "from picamera2 import Picamera2; Picamera2()"

# 7. Full test with all devices
docker run --device /dev/video0 --device /dev/video1 --device /dev/snd \
    -v /sys/dev/char:/sys/dev/char \
    --cap-add SYS_ADMIN \
    --cap-add CAP_SYS_RESOURCE \
    birdstream-pi:latest \
    python3 -c "from picamera2 import Picamera2; print(Picamera2())"
```

---

## Most Likely Solutions (in order of probability)

### Issue 1: Old Python Version (Most Likely)
**Solution:** Try Python 3.11 instead of 3.9
```dockerfile
FROM python:3.11-slim
```

### Issue 2: Missing Compilation During Build
**Solution:** Check for compile errors during docker build
```bash
docker build -t birdstream-pi:latest . 2>&1 | grep -i "error\|failed"
```

### Issue 3: Bookworm vs Bullseye Incompatibility
**Solution:** Use Raspberry Pi OS base image instead
```dockerfile
FROM balena/rpi-raspbian:bullseye
```

### Issue 4: Missing Capabilities in Docker Run
**Solution:** Add all capabilities:
```bash
--device /dev/video0 --device /dev/video1 --device /dev/video2 --device /dev/video3
-v /sys/dev/char:/sys/dev/char
--cap-add SYS_ADMIN
--cap-add CAP_SYS_RESOURCE
```

### Issue 5: picamera2 Can't Access Camera
**Solution:** Use rpicam-vid fallback (see Step 7)

---

## Recommended Next Steps

1. **First:** Try Python 3.11 - it's the most likely fix
   ```bash
   # Edit Dockerfile, change FROM python:3.9-slim to FROM python:3.11-slim
   docker build -t birdstream-pi:latest .
   ```

2. **If that fails:** Run interactive debug shell
   ```bash
   docker run -it birdstream-pi:latest bash
   python3 -c "from picamera2 import Picamera2"
   # See the actual error message
   ```

3. **If still fails:** Check build logs
   ```bash
   docker build -t birdstream-pi:latest . 2>&1 | tail -100
   # Look for error messages during pip install
   ```

4. **Last resort:** Use rpicam-vid fallback

---

## To Test Each Solution

### Test 1: Python 3.11

```bash
# Edit Dockerfile
nano Dockerfile
# Change: FROM python:3.9-slim → FROM python:3.11-slim
# Save and exit

# Rebuild
docker build -t birdstream-pi:latest .

# Test
docker run -it birdstream-pi:latest python3 -c "from picamera2 import Picamera2; print('SUCCESS')"
```

### Test 2: Debug Shell

```bash
docker run -it \
  --device /dev/video0 \
  --device /dev/video1 \
  birdstream-pi:latest \
  bash

# Inside container:
python3 -c "from picamera2 import Picamera2"
# Note any error messages
```

### Test 3: Full Run with All Flags

```bash
docker run \
  --device /dev/video0 \
  --device /dev/video1 \
  --device /dev/video2 \
  --device /dev/video3 \
  --device /dev/snd \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v /sys/dev/char:/sys/dev/char \
  --cap-add SYS_ADMIN \
  --cap-add CAP_SYS_RESOURCE \
  -e PYTHONUNBUFFERED=1 \
  birdstream-pi:latest \
  python main.py
```

---

## Report What You Find

When you run debugging commands, let me know:

1. What Python version is in the container?
2. What error do you get when importing picamera2?
3. What OS/version is on your Pi? (Bullseye or Bookworm?)
4. What Python version is in your Dockerfile?
5. Can you see `/dev/video*` inside the container?

This will help narrow down the exact issue! 🔍
