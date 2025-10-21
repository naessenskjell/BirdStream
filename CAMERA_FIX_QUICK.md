# Camera Fix - Quick Action Plan

## Problem
`picamera2 library not available - running in simulation mode`

## Solution
Use `rpicam-vid` fallback instead - the command you already know works!

---

## Changes Made

✅ **camera_capture.py** - Now supports both:
  - picamera2 (if available)
  - rpicam-vid (fallback)

✅ **Dockerfile** - Now includes:
  - rpicam-apps (provides rpicam-vid command)
  - All other dependencies

---

## What to Do

### Step 1: Rebuild Docker (2-3 minutes)

```bash
cd raspberry-pi
docker build --no-cache -t birdstream-pi:latest .
```

Watch for: `Successfully tagged birdstream-pi:latest`

### Step 2: Verify rpicam-vid is Installed

```bash
docker run birdstream-pi:latest which rpicam-vid
```

Should return: `/usr/bin/rpicam-vid`

### Step 3: Run Full Container

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

### Step 4: Watch for Success

Look for in logs:
```
Using rpicam-vid for camera capture
Camera capture started (rpicam-vid)
Successfully connected to server
Stream transmission started
```

If you see these: **It's working!** ✅

---

## Why This Works

Your reference command was:
```bash
rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o -
```

This works great! The camera_capture.py now:
1. Tries to use picamera2 (Python library)
2. If that fails, automatically uses rpicam-vid (command-line)
3. No manual mode selection needed

---

## Expected Behavior

The system will:
- ✅ Automatically fall back to rpicam-vid
- ✅ Read H.264 video stream from rpicam-vid
- ✅ Buffer frames for encoder
- ✅ Stream to server
- ✅ Show on dashboard

No more "picamera2 not available" errors!

---

## If It Still Doesn't Work

1. **Check logs:** Look for actual error messages
2. **Verify rpicam-vid:** `docker run birdstream-pi:latest rpicam-vid --help`
3. **Check devices:** `docker run --device /dev/video0 birdstream-pi:latest ls -la /dev/video*`

---

## Full Documentation

See `CAMERA_RPICAM_FALLBACK.md` for:
- Detailed explanation
- How rpicam-vid integration works
- Troubleshooting guide
- Performance notes
- Testing checklist

---

**Ready to rebuild?** Start with Step 1! 🚀
