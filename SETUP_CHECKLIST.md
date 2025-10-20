# BirdStream - Setup Checklist & Verification

## Pre-Setup Checklist

### Hardware
- [ ] Raspberry Pi 4 or 5 (2GB+ RAM)
- [ ] Raspberry Pi Camera Module 3 (or v2)
- [ ] USB Microphone (or Pi audio input)
- [ ] Server running Linux (Ubuntu 20.04+)
- [ ] Both on same WiFi network
- [ ] Stable power supply for Pi

### Software Prerequisites
- [ ] Raspberry Pi: Python 3.9+
- [ ] Server: Docker installed (recommended)
- [ ] Both: FFmpeg available or Docker handles it
- [ ] Server: Port 5000 not in use

### Network Setup
- [ ] Server has static IP (e.g., 192.168.0.21)
- [ ] Pi can ping server (`ping 192.168.0.21`)
- [ ] Firewall allows port 5000

---

## Step-by-Step Setup Checklist

### Step 1: Preparation (5 minutes)

- [ ] Clone repository on both Pi and Server
  ```bash
  git clone https://github.com/naessenskjell/BirdStream.git
  ```

- [ ] Know your server IP
  ```bash
  # On server
  hostname -I
  # Copy the IP (e.g., 192.168.0.21)
  ```

- [ ] Create backup of original config
  ```bash
  cp raspberry-pi/config.yaml raspberry-pi/config.yaml.backup
  ```

### Step 2: Configuration (5 minutes)

- [ ] Edit `raspberry-pi/config.yaml`

- [ ] **CRITICAL:** Update server host
  ```yaml
  server:
    host: 192.168.0.21    # ← YOUR SERVER IP
  ```

- [ ] Verify these settings exist
  ```yaml
  reconnect:
    max_retries: 30       # WiFi resilience
  buffer:
    enabled: true         # Frame buffering
  ```

- [ ] Save file

### Step 3: Install Raspberry Pi (5 minutes)

Choose ONE path:

#### Path A: Bare Metal
- [ ] `sudo apt-get update`
- [ ] `sudo apt-get install -y ffmpeg python3-pip`
- [ ] `pip3 install -r requirements.txt`
- [ ] `chmod +x src/main.py`

#### Path B: Docker
- [ ] `docker build -t birdstream-pi:latest .`
- [ ] Test: `docker run ... birdstream-pi:latest` (verify no errors)

### Step 4: Install Server (3 minutes)

#### Path A: Bare Metal
- [ ] `pip3 install -r requirements.txt`
- [ ] Verify Flask installed: `python3 -c "import flask; print('OK')"`

#### Path B: Docker (Recommended)
- [ ] `docker-compose build`
- [ ] `docker-compose up -d`
- [ ] Verify: `docker-compose ps` (shows running)

### Step 5: Start Services (2 minutes)

#### On Raspberry Pi
- [ ] `cd raspberry-pi`
- [ ] `python3 src/main.py`
- [ ] Look for: "Successfully connected to server"
- [ ] Look for: "Stream transmission started"
- [ ] **Important:** Don't close terminal yet!

#### On Server
- [ ] `cd server`
- [ ] If bare metal: `python3 backend/app.py`
- [ ] If Docker: Already running (`docker-compose up -d`)

---

## Verification Checklist

### Phase 1: Network Connectivity (2 minutes)

- [ ] From Pi, test: `ping 192.168.0.21` (should respond)
- [ ] From Pi, test: `curl http://192.168.0.21:5000/health` (should show JSON)
- [ ] From browser, open: `http://192.168.0.21:5000` (should load)

### Phase 2: Dashboard (2 minutes)

- [ ] Dashboard loads at `http://192.168.0.21:5000`
- [ ] Tabs visible: Status, Metrics, Logs, Settings, Images
- [ ] Status tab shows stream state (OFF or LIVE)

### Phase 3: Status Tab (1 minute)

- [ ] Stream state visible (🔴 OFF, 🟢 LIVE, etc.)
- [ ] Video health shows ✓ or ✗
- [ ] Audio health shows ✓ or ✗
- [ ] Control buttons visible: [Stream to YouTube], [Use Static Image], [Turn Off]

### Phase 4: Metrics Tab (1 minute)

- [ ] Bitrate values showing (should be > 0 if streaming)
- [ ] Frame count showing
- [ ] Graphs visible (may be empty on first load)

### Phase 5: Logs Tab (1 minute)

- [ ] Log entries visible
- [ ] Can filter by type
- [ ] Timestamps showing

### Phase 6: API Test (1 minute)

```bash
# From command line:
curl http://192.168.0.21:5000/api/status | jq .

# Should show:
# {
#   "stream_state": "off" or "live",
#   "video_ok": true/false,
#   "audio_ok": true/false,
#   ...
# }
```

- [ ] API returns valid JSON
- [ ] stream_state is not null
- [ ] No error messages

### Phase 7: WiFi Resilience (2 minutes)

**Skip if short on time, verify later**

```bash
# On Pi, check WiFi monitoring enabled
curl http://192.168.0.21:5000/api/status/network | jq .buffer.enabled

# Should show: true
```

- [ ] `buffer.enabled` is true
- [ ] `wifi_disconnections` visible in output
- [ ] `wifi_reconnections` visible in output

---

## Camera & Microphone Verification

### Camera Test

```bash
# On Pi
ls /dev/video*
# Should show: /dev/video0 or similar
```

- [ ] `/dev/video0` or `/dev/video1` exists
- [ ] Can query: `vcgencmd get_camera`
- [ ] Response: `supported=1 detected=1`

### Microphone Test

```bash
# On Pi
arecord -l
# Should list USB Microphone
```

- [ ] USB Microphone appears in list
- [ ] Or correct audio device specified
- [ ] Test record: `arecord -d 2 /tmp/test.wav`
- [ ] File created: `ls -lh /tmp/test.wav` (should be ~200KB)

---

## Troubleshooting Verification

### If Dashboard Won't Load

- [ ] Server running: `curl http://localhost:5000/health` (on server)
- [ ] Port open: `sudo netstat -tlnp | grep 5000`
- [ ] Firewall check: `sudo ufw status`
- [ ] If blocked: `sudo ufw allow 5000/tcp`

### If Status Shows "OFF" Instead of "LIVE"

- [ ] Camera working: `python3 -c "from picamera2 import Picamera2; Picamera2()"`
- [ ] Audio working: `arecord -d 1 /tmp/test.wav && ls /tmp/test.wav`
- [ ] FFmpeg available: `ffmpeg -version`
- [ ] Config server IP correct: `grep "host:" raspberry-pi/config.yaml`

### If Can't Connect to Server

- [ ] Ping server: `ping 192.168.0.21` (from Pi)
- [ ] Server IP correct in config: Check `raspberry-pi/config.yaml`
- [ ] Server running: `curl http://192.168.0.21:5000/health` (from Pi)

### If Metrics Show 0 Bitrate

- [ ] Camera capturing: Check logs for errors
- [ ] FFmpeg running: Check process: `ps aux | grep ffmpeg`
- [ ] Network stream running: Check logs for "Stream transmission started"

---

## Post-Setup Checklist

### Day 1: Functionality

- [ ] Dashboard loads consistently
- [ ] Status shows correct stream state
- [ ] Metrics update when streaming
- [ ] No error messages in logs

### Day 2-3: Configuration

- [ ] (Optional) Add YouTube stream key
  - [ ] Dashboard Settings tab
  - [ ] Paste stream key
  - [ ] Test connection
  - [ ] Check YouTube Live tab

- [ ] (Optional) Upload fallback image
  - [ ] Dashboard Images tab
  - [ ] Upload JPG (max 10MB)
  - [ ] Click [Select]

### Day 4-7: Stability

- [ ] Run for 24 hours, check logs
  - [ ] No errors
  - [ ] Bitrates stable
  - [ ] No disconnections

- [ ] Test WiFi resilience (optional)
  - [ ] Simulate outage: `sudo ip link set wlan0 down`
  - [ ] Watch logs for buffering
  - [ ] Recovery: `sudo ip link set wlan0 up`
  - [ ] Verify buffered_frames_sent > 0

### Ongoing: Monitoring

- [ ] Monitor logs daily
  - [ ] `tail -f /var/log/birdstream.log`
  - [ ] Look for ERROR or WARNING

- [ ] Check metrics weekly
  - [ ] Dashboard Metrics tab
  - [ ] Bitrates normal
  - [ ] Frame count > 0

---

## Configuration Verification

### Minimum Required
- [ ] Server IP set in config.yaml
- [ ] FFmpeg available on both Pi and Server
- [ ] Python 3.9+ on both
- [ ] Port 5000 accessible
- [ ] Dependencies installed

### Recommended Settings
- [ ] `max_retries: 30` (WiFi resilience)
- [ ] `buffer.enabled: true` (Frame preservation)
- [ ] `monitor_enabled: true` (WiFi monitoring)

### Optional Customization
- [ ] Camera bitrate (if WiFi unstable)
- [ ] YouTube stream key (if streaming to YouTube)
- [ ] Fallback image (if WiFi often fails)

---

## Success Criteria

### Minimal Success (Basics Working)
- ✅ Dashboard loads
- ✅ Status shows state
- ✅ Can start/stop stream
- ✅ No crash on startup

### Full Success (Everything Working)
- ✅ All above +
- ✅ Metrics showing data
- ✅ Logs showing events
- ✅ WiFi monitoring active
- ✅ YouTube streaming works (optional)

### Advanced Success (Optimized)
- ✅ All above +
- ✅ WiFi resilience tested
- ✅ Bitrate optimized for your network
- ✅ 24+ hour stability verified
- ✅ Fallback image configured

---

## Common Gotchas to Avoid

- [ ] ❌ Don't forget to edit server IP in config.yaml
- [ ] ❌ Don't use `localhost` in config (Pi can't reach it)
- [ ] ❌ Don't forget to install dependencies
- [ ] ❌ Don't close Pi terminal during setup
- [ ] ❌ Don't forget firewall rules on server
- [ ] ❌ Don't expect video without camera detected
- [ ] ❌ Don't expect audio without microphone detected

---

## Documentation References

If you get stuck at any step:

| Problem | Doc to Check |
|---------|--------------|
| How do I set it up? | QUICK_START.md |
| Need more detail | QUICK_START.md Step-by-step |
| Verification failing | SETUP_TIPS.md Troubleshooting |
| WiFi issues | WIFI_QUICK_REF.md |
| Dashboard won't load | SETUP_TIPS.md Red Flags |
| Camera/audio not detected | SETUP_TIPS.md Mistake 4 |
| WiFi keeps disconnecting | SETUP_TIPS.md Mistake 5 |
| Need to optimize | SETUP_TIPS.md Environment Tuning |

---

## Final Checklist: Ready to Deploy?

Before going to production:

- [ ] Setup checklist 100% complete
- [ ] Verification checklist 100% complete
- [ ] Camera and microphone verified
- [ ] Dashboard loading without errors
- [ ] API responding to requests
- [ ] 24+ hours runtime without errors
- [ ] WiFi resilience tested (optional but recommended)
- [ ] YouTube streaming configured (if using)
- [ ] Fallback image uploaded (if using)
- [ ] Logs monitored for issues
- [ ] Performance acceptable
- [ ] Ready for production!

---

## Quick Reference: Essential Commands

### Connection Testing
```bash
ping 192.168.0.21                    # Can reach server?
curl http://192.168.0.21:5000/health # Server running?
curl http://192.168.0.21:5000/api/status # Status?
```

### Device Testing
```bash
vcgencmd get_camera                  # Camera detected?
arecord -l                           # Microphone detected?
ffmpeg -version                      # FFmpeg installed?
python3 -c "import picamera2; print('OK')" # Dependencies?
```

### Monitoring
```bash
tail -f /var/log/birdstream.log      # Watch logs
ps aux | grep python3                # Process running?
lsof -i :5000                        # Port in use?
```

### Control
```bash
Ctrl+C                               # Stop service
python3 src/main.py                  # Start Pi service
python3 backend/app.py               # Start Server service
```

---

**Print this checklist and cross off each item as you complete setup!** ✓
