# Fix picamera2 Docker Issue - Quick Steps

## The Problem
```
WARNING:root:picamera2 not available - running in simulation mode
```

This means the Python `picamera2` module isn't being found/imported in Docker.

---

## Quick Fix #1: Update Python Version (Most Likely to Work)

I've already updated the Dockerfile to use Python 3.11 instead of 3.9.

**Rebuild the image:**
```bash
cd raspberry-pi
docker build --no-cache -t birdstream-pi:latest .
```

**Then test:**
```bash
docker run --device /dev/video0 \
  birdstream-pi:latest \
  python main.py
```

If this doesn't show the "not available" warning, you're good! ✅

---

## Quick Fix #2: If that Doesn't Work

Run a debug shell to see the actual error:

```bash
docker run -it birdstream-pi:latest bash
```

Inside the container, run:
```bash
python3 -c "from picamera2 import Picamera2; print('OK')"
```

Copy the exact error message you get and share it with me.

---

## Quick Fix #3: Full Docker Run with All Flags

Use this command with all device access and capabilities:

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

This ensures all video devices and capabilities are properly mounted.

---

## Troubleshooting Priority

1. **First try:** `docker build --no-cache` and run with updated Dockerfile (Python 3.11)
2. **If fails:** Run debug shell and copy error message
3. **If still fails:** Use full docker run command with all flags above
4. **Last resort:** See PI_DOCKER_DEBUG.md for alternative solutions

---

## What Changed

**File:** `raspberry-pi/Dockerfile`
- Changed: `FROM python:3.9-slim` → `FROM python:3.11-slim`
- Reason: Python 3.11 has better picamera2 compatibility

That's it! Rebuild and test. 🚀
