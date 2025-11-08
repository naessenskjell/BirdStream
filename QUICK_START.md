 # BirdStream - Quick Start (updated)

 This quick start shows the minimal, current steps to get a Raspberry Pi camera + USB microphone streaming to your server and the dashboard. It uses the Raspberry Pi native install/deploy flow (see `raspberry-pi/deploy_pi.md`) and the server-side Docker Compose stack which includes an nginx-rtmp ingest on port 1935 and the Flask dashboard on port 5000.

 ## What this doc covers (short)
 - Pi: native install (recommended) — follow `raspberry-pi/deploy_pi.md` for full Pi-side details
 - Server: Docker Compose with `nginx-rtmp` (RTMP ingest on 1935) and Flask on 5000

 ---

 ## Step 1 — Clone repository (Pi & Server)

 ```powershell
 git clone https://github.com/naessenskjell/BirdStream.git
 cd BirdStream
 ```

 ---

 ## Step 2 — Raspberry Pi (native install)

 Important: the Pi capture must run natively (not in a Docker container) to access libcamera and hardware acceleration reliably. See the full Pi deploy doc at `raspberry-pi/deploy_pi.md` for detailed, tested steps; below are the essentials.

 1) Update OS 

 ```bash
 sudo apt update
 sudo apt upgrade -y
 ```

 2) Edit `raspberry-pi/config.yaml` — critical values

Example (critical bits):

 ```yaml
 server:
   host: 192.168.0.21    # YOUR server IP
   rtmp_port: 1935       # RTMP ingest (nginx-rtmp)
   api_port: 5000        # Flask API/dashboard
   reconnect:
     max_retries: 60
     initial_delay: 1
     max_delay: 45
 buffer:
   enabled: true
   max_frames: 1800      # e.g. 1800 frames ~1 minute at 30fps
 camera:
   bitrate: 4000
   fps: 30
 ```


 3) Run the setup script

 ```bash
 cd raspberry-pi
  sudo bash setup_pi.sh
 ```

 4) Run BirdStream manually (for debugging)
  ```bash
  bash run_birdstream.sh
  ```

 5) Install systemd service (optional, to run on boot)

 ```bash
 sudo cp deploy/birdstream.service /etc/systemd/system/birdstream.service
 sudo systemctl daemon-reload
 sudo systemctl enable --now birdstream.service
 ```

 ---

 ## Step 3 — Server: Docker Compose 

 The server stack now uses Docker Compose. The RTMP ingest is provided by an `nginx-rtmp` service (binds port 1935). The Flask dashboard/API remains on port 5000.

 1) Start the Docker Compose stack

 ```bash
 cd server
 docker-compose build
 docker-compose up -d
 docker-compose ps
 ```

 The compose stack includes:
 - `nginx-rtmp` listening on host:1935 (RTMP ingest `/live`)
 - `flask` backend listening on host:5000 (HTTP API/dashboard)

 2) Verify services

 ```bash
 # Check RTMP status page (nginx-rtmp exposes an HTTP status on 8080 by default in the compose setup)
 curl http://localhost:8080

 # Check Flask health
 curl http://localhost:5000/health
 ```

 ---

 ## Step 4 — Quick verification

 1) Test RTMP ingest (from any machine with ffmpeg)

 ```bash
 # Send a short test stream to the server RTMP ingest
 ffmpeg -f lavfi -i testsrc=size=640x360:rate=25 -f lavfi -i anullsrc=r=48000 -c:v libx264 -t 10 -b:v 800k -c:a aac -ar 48000 -f flv rtmp://192.168.0.21:1935/live/test
 ```

 If successful, ffmpeg will show RTMP frames being sent and nginx-rtmp will accept the connection.

 2) From the Pi: test camera and microphone locally

 ```bash
 # Camera
 python3 -c "from picamera2 import Picamera2; print('OK' if Picamera2() else 'FAIL')"

 # Microphone (record 2s)
 arecord -d 2 /tmp/test.wav
 ls -lh /tmp/test.wav
 ```

 ## Step 5 — Check the dashboard

 Open the dashboard in a browser:

 ```
 http://192.168.0.21:5000
 ```

 The dashboard talks to the Flask API on port 5000. The RTMP ingest is separate and handled by nginx-rtmp on 1935.

 ---

 ## Files & locations (quick)

 - Pi config: `raspberry-pi/config.yaml`
 - Pi code: `raspberry-pi/src/` (camera_capture.py, audio_capture.py, stream_encoder.py, main.py)
 - Pi deploy helpers: `raspberry-pi/deploy_pi.md`, `raspberry-pi/install_asound.sh`, `raspberry-pi/deploy/`
 - Server: `server/` (docker-compose.yml, backend/, frontend/, nginx/)

 