# BirdStream - Setup Tips & Gotchas

## Critical: Don't Miss These

### 🔴 Must Edit: Server IP in config.yaml

```yaml
server:
  host: 192.168.0.21    # ← CHANGE THIS to your server's actual IP
```

**Check your server IP:**

```bash
# On server machine
hostname -I
# Example output: 192.168.0.21 192.168.1.50

# Use the IP on your WiFi network (usually 192.168.x.x)
```

**If you get wrong IP:** Pi will never connect, no streaming.

---

### 🔴 Must Have: FFmpeg on Both Pi and Server

**On Raspberry Pi:**

```bash
sudo apt-get install ffmpeg
# Verify
ffmpeg -version | head -1
```

**On Server:**

```bash
sudo apt-get install ffmpeg
# Or via Docker (included in Dockerfile)
```

**If missing:** Encoder will fail silently or crash.

---

### 🔴 Must Allow: Port 5000 on Server

```bash
# Check if open
sudo ufw status

# If not open
sudo ufw allow 5000/tcp
sudo ufw reload

# Verify
sudo netstat -tlnp | grep 5000
# Should show: LISTEN
```

**If blocked:** Dashboard won't load, can't stream.

---

## Common Setup Mistakes

### ❌ Mistake 1: Wrong IP Address

```yaml
# ❌ WRONG
server:
  host: localhost        # Won't work on Pi!
  host: 127.0.0.1       # Won't work on Pi!
  host: 192.168.1.100   # Wrong subnet?

# ✅ CORRECT
server:
  host: 192.168.0.21    # Your actual server IP
```

**How to find it:**

```bash
# On the server machine
ip addr show | grep "inet "
# Look for: inet 192.168.x.x
```

---

### ❌ Mistake 2: Firewall Blocking

**Symptom:** Dashboard loads but no status data

**Fix:**

```bash
# Check firewall
sudo ufw status
# If status says "inactive", you're good
# If "active":

sudo ufw allow 5000/tcp
sudo ufw allow 22/tcp    # SSH
sudo ufw reload
```

---

### ❌ Mistake 3: Dependencies Not Installed

**Symptom:** Module not found errors

**Raspberry Pi:**

```bash
cd raspberry-pi

# Install ALL requirements
pip3 install -r requirements.txt

# Verify key ones
python3 -c "import picamera2; print('✓ picamera2')"
python3 -c "import pyaudio; print('✓ pyaudio')"
python3 -c "import yaml; print('✓ pyyaml')"
```

**Server:**

```bash
cd server

pip3 install -r requirements.txt

# Verify
python3 -c "import flask; print('✓ flask')"
python3 -c "import socketio; print('✓ flask-socketio')"
```

---

### ❌ Mistake 4: Camera/Microphone Not Detected

**Symptom:** App starts but no video/audio

**Check Camera:**

```bash
# List video devices
ls /dev/video*
# Should show: /dev/video0 or /dev/video1

# If not found
vcgencmd get_camera
# Expected: supported=1 detected=1

# Enable camera if needed
sudo raspi-config
# Interface Options → Camera → Enable
```

**Check Microphone:**

```bash
# List audio devices
arecord -l
# Should show your USB microphone

# If not found
# 1. Plug in USB mic
# 2. Run: arecord -l
# 3. Specify in config.yaml: device: "default" or name
```

---

### ❌ Mistake 5: Wrong Bitrate for WiFi

**Symptom:** Constant disconnections, buffering

**If WiFi is unstable:**

```yaml
camera:
  bitrate: 2500    # Reduce from 4000
  # or even 1500 if really bad
```

**Rule of thumb:**
- Stable WiFi (5GHz, close): 4000 kbps ✓
- Medium WiFi (2.4GHz): 3000 kbps
- Unstable WiFi: 1500-2000 kbps

---

### ❌ Mistake 6: Buffer Settings Too Low

**Symptom:** WiFi outage causes immediate stream death

**Don't do this:**

```yaml
# ❌ Bad for WiFi
buffer:
  enabled: false           # Never!
  max_frames: 50           # Too small
  memory_limit_mb: 10      # Too small
```

**Use defaults:**

```yaml
# ✅ Good for WiFi
buffer:
  enabled: true
  max_frames: 450          # ~15 seconds
  memory_limit_mb: 256     # Safe on Pi
```

---

## Best Practices

### 1. Start Simple

Test on **local network first** before adding YouTube:

```
Camera → Pi → Server (local)
         (test here first)
              ↓
         (then add) → YouTube
```

### 2. Monitor Logs During Setup

Keep two terminals open:

```bash
# Terminal 1: Start app
cd raspberry-pi
python3 src/main.py

# Terminal 2: Watch logs
tail -f /var/log/birdstream.log
```

Look for:

```
✓ "Successfully connected to server"
✓ "Stream transmission started"
✗ "Failed to connect" → Server IP wrong
✗ "No module named" → Dependencies missing
```

### 3. Use Dashboard Status Tab

Open dashboard and check Status tab:

| Status | Meaning | Action |
|--------|---------|--------|
| 🔴 OFF | Not streaming | Click "Stream to YouTube" or "Use Static Image" |
| 🟢 LIVE | Streaming to YouTube | Working! |
| 🟡 RECONNECTING | Lost server connection | Wait for recovery |
| 🟣 STATIC | Using fallback image | WiFi outage, waiting |
| 🔴 ERROR | Something failed | Check logs |

### 4. Test WiFi Resilience

After everything works:

```bash
# Simulate WiFi outage
sudo ip link set wlan0 down

# Watch logs for buffering
tail -f /var/log/birdstream.log | grep -E "WiFi|Buffer|Reconnect"

# After 1-2 minutes, bring back
sudo ip link set wlan0 up

# Check recovery
curl http://192.168.0.21:5000/api/status/network | jq .buffer.buffered_frames_sent
# Should show non-zero if frames were buffered
```

### 5. Use systemd for Auto-Start (Pi)

Create `/etc/systemd/system/birdstream.service`:

```ini
[Unit]
Description=BirdStream Streaming Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/BirdStream/raspberry-pi
ExecStart=/usr/bin/python3 /home/pi/BirdStream/raspberry-pi/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl enable birdstream
sudo systemctl start birdstream
sudo systemctl status birdstream
```

### 6. Use Docker for Production

More reliable than bare metal:

```bash
cd server
docker-compose up -d --restart unless-stopped

# Check logs
docker-compose logs -f
```

---

## Environment-Specific Tuning

### Setup: Single Room WiFi

```yaml
camera:
  bitrate: 4000           # Full quality OK
  
server:
  reconnect:
    max_retries: 10       # Quick failover
```

### Setup: Outdoor/Distant WiFi

```yaml
camera:
  bitrate: 1500           # Lower quality
  fps: 15                 # Lower framerate
  
server:
  reconnect:
    max_retries: 60       # More attempts
    initial_delay: 1      # Quick retries
  buffer:
    max_frames: 900       # 30 seconds
    memory_limit_mb: 512  # If Pi has RAM
```

### Setup: Ethernet (Rock Solid)

```yaml
camera:
  bitrate: 8000           # Ultra HD
  fps: 60                 # Smooth
  
server:
  reconnect:
    max_retries: 5        # Fail fast
  buffer:
    enabled: false        # Not needed
```

---

## Testing Checklist

### Phase 1: Basic Connectivity

- [ ] Pi can ping server: `ping 192.168.0.21`
- [ ] Server running: `curl http://192.168.0.21:5000/health`
- [ ] API responding: `curl http://192.168.0.21:5000/api/status`

### Phase 2: Component Testing

- [ ] Camera detected: `python3 -c "from picamera2 import Picamera2; Picamera2()"`
- [ ] Microphone detected: `arecord -l`
- [ ] FFmpeg available: `ffmpeg -version`

### Phase 3: Integration

- [ ] Pi app starts: `python3 src/main.py`
- [ ] Dashboard loads: Open http://192.168.0.21:5000
- [ ] Status shows LIVE: Check Status tab

### Phase 4: WiFi Resilience

- [ ] Buffer enabled: Check config.yaml
- [ ] Monitor thread running: Check logs for "Network monitor"
- [ ] Simulated outage works:
  ```bash
  sudo ip link set wlan0 down
  # Wait 30 seconds
  sudo ip link set wlan0 up
  # Check buffered_frames_sent increased
  ```

---

## Performance Reference

### Expected CPU Usage

```
Raspberry Pi:
  Camera capture:     ~10%
  Audio capture:      ~5%
  FFmpeg encode:      ~30% (H.264 hw accelerated)
  Network stream:     ~5%
  WiFi monitor:       <1%
  ─────────────────────────
  Total:              ~50%
  
Safe margin: <80% recommended
```

### Expected Memory Usage

```
Raspberry Pi:
  Python runtime:     ~30MB
  Camera buffers:     ~50MB
  FFmpeg:             ~100MB
  Frame buffer:       ~10MB (typical, up to 256MB max)
  ─────────────────────────
  Total:              ~200MB
  
Safe on Pi 4GB+
```

### Expected Network Usage

```
Video:              4000 kbps = 500 KB/s
Audio:              128 kbps = 16 KB/s
─────────────────────────────────
Per second:         516 KB/s
Per minute:         31 MB
Per hour:           1.9 GB

WiFi minimum:       5 Mbps (1.25x bitrate for headroom)
```

---

## Staying Organized

### Logs Location

```
Raspberry Pi:  /var/log/birdstream.log
Server:        stdout or logs/ directory

# Tail in real-time
tail -f /var/log/birdstream.log

# Filter for errors
grep ERROR /var/log/birdstream.log

# Watch WiFi events
tail -f /var/log/birdstream.log | grep -E "WiFi|Buffer|Reconnect"
```

### Config Backup

Before making changes:

```bash
cp raspberry-pi/config.yaml raspberry-pi/config.yaml.backup

# If something breaks
cp raspberry-pi/config.yaml.backup raspberry-pi/config.yaml
```

---

## Red Flags

If you see these, something's wrong:

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` | Server not running | Start Flask/docker-compose |
| `Name or service not known` | Server IP wrong | Check config.yaml |
| `No module named picamera2` | Dependencies missing | `pip3 install -r requirements.txt` |
| `Permission denied /dev/video0` | Camera access denied | `sudo usermod -a -G video $USER` |
| `ALSA lib errors` | Audio driver warnings | Ignore (expected on Pi) |
| `Buffer full` | WiFi outage too long | Increase `max_frames` |
| `Max retries exceeded` | Server unreachable too long | Check server IP/firewall |

---

## Success Indicators

✅ You're set up correctly if you see:

1. Dashboard loads at http://server-ip:5000
2. Status tab shows stream state (OFF, LIVE, RECONNECTING, etc.)
3. Metrics show video/audio bitrates > 0
4. Logs show no ERROR messages
5. WiFi test: Can simulate outage, see buffering, verify recovery
6. API calls work: `curl http://server-ip:5000/api/status`

---

## Quick Reference

### Most Common Commands

```bash
# Check if Pi can reach server
ping 192.168.0.21

# Check if server API responding
curl http://192.168.0.21:5000/api/status

# Check network status
curl http://192.168.0.21:5000/api/status/network | jq .

# Watch logs in real-time
tail -f /var/log/birdstream.log

# Restart app (Ctrl+C first, then)
python3 src/main.py

# Check what's using port 5000
lsof -i :5000

# Kill stuck process
pkill -f "python3 src/main.py"
```

---

**When in doubt, check the logs!** 🔍
