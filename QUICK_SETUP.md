# BirdStream - 5-Minute Setup

## What You're Installing

A system that:
- Captures video from Raspberry Pi camera
- Sends it to a server
- Streams to YouTube (optional)
- Survives WiFi outages automatically

---

## Hardware Check (2 minutes)

### Raspberry Pi Side
```
✓ Raspberry Pi 4/5 (2GB+ RAM)
✓ Camera Module 3 (or v2)
✓ USB Microphone (or analog audio)
✓ Connected to WiFi
```

### Server Side
```
✓ Linux server with Docker (Ubuntu recommended)
✓ Connected to same WiFi network
✓ Port 5000 available
```

---

## Setup (5 minutes)

### Step 1: Clone & Configure (1 min)

```bash
# On BOTH Pi and Server
git clone https://github.com/naessenskjell/BirdStream.git
cd BirdStream

# On Pi, edit config
nano raspberry-pi/config.yaml

# Change this ONE line:
server:
  host: 192.168.0.21    # ← YOUR SERVER IP HERE
```

**To find your server IP:**
```bash
# On server machine
hostname -I
# Copy the IP (usually 192.168.x.x)
```

### Step 2: Install on Pi (2 min)

```bash
cd BirdStream/raspberry-pi

# System packages
sudo apt-get update
sudo apt-get install -y ffmpeg python3-pip

# Python packages
pip3 install -r requirements.txt
```

### Step 3: Install on Server (1 min)

```bash
cd BirdStream/server

# With Docker (easiest)
docker-compose up -d

# OR without Docker
pip3 install -r requirements.txt
python3 backend/app.py &
```

### Step 4: Start (1 min)

```bash
# On Pi
cd BirdStream/raspberry-pi
python3 src/main.py

# On Server (if not using Docker)
cd BirdStream/server
python3 backend/app.py
```

---

## Verify It Works (1 minute)

### From Pi
```bash
# Should connect to server without errors
# Look for: "Successfully connected to server"
# Look for: "Stream transmission started"
```

### From Your Browser
```
http://192.168.0.21:5000
```

Check:
- Status tab shows 🟢 LIVE or 🔴 OFF
- Metrics tab shows numbers > 0

### From Command Line
```bash
curl http://192.168.0.21:5000/api/status | grep -o '"stream_state":"[^"]*"'
# Expected: "stream_state":"live" or "stream_state":"off"
```

---

## That's It! 🎉

Your system is now running with:
- ✅ Live video/audio capture
- ✅ WiFi outage resilience (15-second buffer)
- ✅ Automatic server reconnection (30 attempts)
- ✅ Web dashboard
- ✅ YouTube streaming ready (add key later)

---

## Next Steps (Optional)

### Add YouTube Streaming
1. Get stream key from YouTube Studio
2. Dashboard → Settings → Paste key → Save
3. Dashboard → Status → [▶ Stream to YouTube]

### Upload Fallback Image
1. Dashboard → Images → Upload
2. Click [Select] to activate
3. Used automatically if WiFi fails

### Monitor WiFi Resilience
```bash
# Simulate WiFi outage
sudo ip link set wlan0 down
# Wait 30 seconds, check logs for buffering
sudo ip link set wlan0 up
# Verify recovery
```

---

## Troubleshooting (3 Problems)

### Problem 1: Dashboard Won't Load
```bash
# Check if server running
curl http://192.168.0.21:5000/health

# If fails, server not started
cd BirdStream/server
python3 backend/app.py
```

### Problem 2: No Stream (Status shows OFF)
```bash
# Check Pi logs for errors
tail /var/log/birdstream.log | grep ERROR

# Most common: Wrong server IP
# Fix in: raspberry-pi/config.yaml
# server.host = 192.168.0.21
```

### Problem 3: WiFi Disconnects Often
```yaml
# Edit config.yaml:
camera:
  bitrate: 2000  # Reduce from 4000
```

---

## File Locations

```
You need to edit:   raspberry-pi/config.yaml
                    (only the server: host line)

Main files:
  Raspberry Pi:     raspberry-pi/src/main.py
  Server:           server/backend/app.py
  Dashboard:        server/frontend/index.html

Logs:
  Raspberry Pi:     /var/log/birdstream.log
  Server:           stdout (when running manually)
```

---

## Critical Settings

```yaml
# raspberry-pi/config.yaml

server:
  host: 192.168.0.21       # MUST be your server IP
  reconnect:
    max_retries: 30        # WiFi outage resilience (10 min)
  buffer:
    enabled: true          # Frame buffering during outages
    max_frames: 450        # ~15 seconds of video

camera:
  bitrate: 4000            # Mbps (reduce if WiFi unstable)
```

---

## Commands Cheat Sheet

```bash
# Check setup
ping 192.168.0.21                    # Can reach server?
curl http://192.168.0.21:5000/health # Server running?

# Monitor
tail -f /var/log/birdstream.log      # Watch logs
curl http://192.168.0.21:5000/api/status | jq . # Status

# Test WiFi resilience
sudo ip link set wlan0 down          # Outage
sudo ip link set wlan0 up            # Recovery

# Restart
pkill -f "python3 src/main.py"       # Stop Pi
python3 src/main.py                  # Start Pi
```

---

## Performance

```
CPU:        ~50% on Pi (normal)
Memory:     ~200MB Pi, ~100MB Server
Bandwidth:  ~2 GB per hour

WiFi needed: 5+ Mbps
Latency:     50-500ms typical
```

---

Done! Your BirdStream is ready. 🚀
