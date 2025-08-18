# BirdStream - Camera to Server Streaming System

## Architecture Overview

This system streams video from a Raspberry Pi camera to a remote server using SRT (Secure Reliable Transport) protocol for robust transmission over unreliable networks.

**Flow:**
1. **Camera (Raspberry Pi)**: Captures video/audio → Local RTSP streams → Combined stream → SRT transmission to server
2. **Server**: Receives SRT stream → Converts to local RTSP → YouTube streaming processor

## Hardware

- Raspberry Pi 3B+
- Camera Module 3 Wide
- USB Microphone (mono input, converted to stereo)
- Power supply, fan, ...

## Main Streaming Workflow: Camera to Server via SRT

The complete workflow streams from the Raspberry Pi camera to a remote server using SRT for reliable transmission over unstable networks.

### Camera Side (Raspberry Pi)

#### 1. Stream Video Only (Local RTSP)

```sh
rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o - \
| ffmpeg -nostdin -thread_queue_size 512 -fflags +genpts -re -i - \
  -c:v copy -an \
  -f rtsp rtsp://localhost:8554/video
```

- `-an`: disables audio in the video stream.

#### 2. Stream Audio Only (Local RTSP with Mono to Stereo Conversion)

```sh
ffmpeg -nostdin -f alsa -channels 1 -ar 44100 -i hw:1,0 \
  -af "volume=2.0,pan=stereo|c0=c0|c1=c0" \
  -c:a aac -ar 44100 -b:a 128k \
  -vn \
  -f rtsp rtsp://localhost:8554/audio
```

- `-vn`: disables video in the audio stream.
- `pan=stereo|c0=c0|c1=c0`: converts mono input to stereo by duplicating the mono channel.

#### 3. Combine Video and Audio Streams (Local RTSP)

```sh
ffmpeg -i rtsp://localhost:8554/video -i rtsp://localhost:8554/audio \
  -c:v copy -c:a copy \
  -f rtsp rtsp://localhost:8554/cam
```

#### 4. Send Combined Stream to Server via SRT

```sh
ffmpeg -rtsp_transport tcp -i rtsp://localhost:8554/cam \
  -c:v copy -c:a aac -b:a 96k \
  -f mpegts "srt://YOUR_SERVER_IP:9710?mode=caller&latency=10000&rcvbuf=20000000&sndbuf=20000000"
```

Replace `YOUR_SERVER_IP` with your server's IP address.

**SRT Parameters for Maximum Robustness:**
- `latency=10000`: 10s buffer for network jitter and packet loss recovery
- `rcvbuf=20000000` & `sndbuf=20000000`: Large 20MB buffers for stability over varying network conditions
- `mode=caller`: Camera initiates the connection to the server

**Why this architecture?**

- **Local RTSP streams**: Isolates video and audio pipelines for easier troubleshooting and flexibility.
- **SRT transmission**: Provides reliable streaming over unreliable networks with automatic retransmission and adaptive bitrate.
- **High-latency buffering**: 10s latency and large buffers prioritize stability over real-time performance.
- **Video copy optimization**: No CPU-intensive re-encoding, using direct video copy for better performance.
- **Separate processing stages**: Allows independent restarts and monitoring of each component.

### Server Side

#### 1. Receive SRT Stream and Convert to RTSP

On the server, receive the SRT stream from the camera and convert it to RTSP for local processing:

```sh
ffmpeg \
  -itsoffset 10 -i "srt://0.0.0.0:9710?mode=listener&latency=10000&rcvbuf=20000000&sndbuf=20000000" \
  -i "srt://0.0.0.0:9710?mode=listener&latency=10000&rcvbuf=20000000&sndbuf=20000000" \
  -map 0:v -map 1:a \
  -c:v copy -c:a aac -bsf:a aac_adtstoasc \
  -f rtsp rtsp://127.0.0.1:8554/live
```

This command:
- Listens for SRT connections on port 9710 (`mode=listener`)
- Applies a 10-second offset for stability (`-itsoffset 10`)
- Adds AAC headers for RTSP compatibility with `-bsf:a aac_adtstoasc`
- Outputs the combined stream as RTSP to `rtsp://127.0.0.1:8554/live` for local processing

#### 2. Create Systemd Service for SRT-to-RTSP Conversion

Create `/etc/systemd/system/srt-to-rtsp.service`:

```ini
[Unit]
Description=SRT to RTSP Stream Converter
After=network.target mediamtx.service

[Service]
ExecStart=/bin/bash -c 'ffmpeg -itsoffset 10 -i "srt://0.0.0.0:9710?mode=listener&latency=10000&rcvbuf=20000000&sndbuf=20000000" -i "srt://0.0.0.0:9710?mode=listener&latency=10000&rcvbuf=20000000&sndbuf=20000000" -map 0:v -map 1:a -c:v copy -c:a aac -bsf:a aac_adtstoasc -f rtsp rtsp://localhost:8554/cam'
Restart=always
RestartSec=5
User=admin

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```sh
sudo systemctl enable srt-to-rtsp
sudo systemctl start srt-to-rtsp
```

---

## Setting up MediaMTX (Camera Side)

MediaMTX acts as a robust RTSP server on the Raspberry Pi to manage local streams before SRT transmission.

### 1. Install MediaMTX

```sh
wget https://github.com/bluenviron/mediamtx/releases/latest/download/mediamtx_linux_armv7.tar.gz
tar xvf mediamtx_linux_armv7.tar.gz
sudo mv mediamtx /usr/local/bin/
```

### 2. Configure MediaMTX

Edit your `mediamtx.yml`:

```yaml
paths:
  video:
    source: publisher
  audio:
    source: publisher  
  cam:
    source: publisher
```

This allows the various ffmpeg processes to publish to the `/video`, `/audio`, and `/cam` paths.

### 3. Start MediaMTX

```sh
./mediamtx /path/to/mediamtx.yml
```

### 4. Autostart MediaMTX

Create a systemd service file:

```sh
sudo nano /etc/systemd/system/mediamtx.service
```

Paste:

```ini
[Unit]
Description=MediaMTX RTSP Server
After=network.target

[Service]
ExecStart=/path/to/mediamtx /path/to/mediamtx.yml
Restart=always
RestartSec=5
User=admin

[Install]
WantedBy=multi-user.target
```

Create the configuration directory and file:

```sh
sudo mkdir -p /etc/mediamtx
sudo nano /etc/mediamtx/mediamtx.yml
```

Add the MediaMTX configuration:

```yaml
paths:
  video:
    source: publisher
  audio:
    source: publisher  
  cam:
    source: publisher
```

Enable and start the service:

```sh
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
```

---

## Autostarting Camera Streams with systemd (Camera Side)

To automatically start the camera streaming pipeline on boot, create the following systemd service files on the Raspberry Pi.

### 1. Video Stream Service

```ini
[Unit]
Description=FFmpeg RTSP Video Stream
After=network.target mediamtx.service

[Service]
ExecStart=/bin/bash -c 'rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o - | ffmpeg -nostdin -thread_queue_size 512 -fflags +genpts -re -i - -c:v copy -an -f rtsp rtsp://localhost:8554/video'
Restart=always
RestartSec=5
User=admin

[Install]
WantedBy=multi-user.target
```

Save as `/etc/systemd/system/ffmpeg-video.service`.

### 2. Audio Stream Service (with Mono to Stereo Conversion)

```ini
[Unit]
Description=FFmpeg RTSP Audio Stream
After=network.target mediamtx.service

[Service]
ExecStart=/bin/bash -c 'ffmpeg -nostdin -f alsa -channels 1 -ar 44100 -i hw:1,0 -af "volume=2.0,pan=stereo|c0=c0|c1=c0" -c:a aac -ar 44100 -b:a 128k -vn -f rtsp rtsp://localhost:8554/audio'
Restart=always
RestartSec=5
User=admin

[Install]
WantedBy=multi-user.target
```

Save as `/etc/systemd/system/ffmpeg-audio.service`.

### 3. Combined Stream Service

```ini
[Unit]
Description=FFmpeg RTSP Combined Stream (Video + Audio)
After=network.target ffmpeg-video.service ffmpeg-audio.service

[Service]
ExecStart=/bin/bash -c 'ffmpeg -i rtsp://localhost:8554/video -i rtsp://localhost:8554/audio -fflags +genpts -avoid_negative_ts make_zero -c:v copy -c:a copy -f rtsp rtsp://localhost:8554/cam'
Restart=always
RestartSec=5
User=admin

[Install]
WantedBy=multi-user.target
```

Save as `/etc/systemd/system/ffmpeg-combined.service`.

### 4. SRT Transmission Service

```ini
[Unit]
Description=SRT Stream Transmission to Server
After=network.target ffmpeg-combined.service

[Service]
ExecStart=/bin/bash -c 'ffmpeg -rtsp_transport tcp -i rtsp://localhost:8554/cam -c:v copy -c:a aac -b:a 96k -f mpegts "srt://YOUR_SERVER_IP:9710?mode=caller&latency=10000&rcvbuf=20000000&sndbuf=20000000"'
Restart=always
RestartSec=5
User=admin

[Install]
WantedBy=multi-user.target
```

Replace `YOUR_SERVER_IP` with your server's IP address. Save as `/etc/systemd/system/srt-transmission.service`.

**For even more stability, you can increase latency further:**
```ini
[Service]
ExecStart=/bin/bash -c 'ffmpeg -rtsp_transport tcp -i rtsp://localhost:8554/cam -c:v copy -c:a aac -b:a 96k -f mpegts "srt://YOUR_SERVER_IP:9710?mode=caller&latency=10000&rcvbuf=20000000&sndbuf=20000000"'
```

This provides 10-second buffering with 20MB buffers for maximum robustness over poor network conditions.

### Enable and Start Services (Camera Side)

```sh
sudo systemctl enable mediamtx
sudo systemctl enable ffmpeg-video
sudo systemctl enable ffmpeg-audio
sudo systemctl enable ffmpeg-combined
sudo systemctl enable srt-transmission

sudo systemctl start mediamtx
sudo systemctl start ffmpeg-video
sudo systemctl start ffmpeg-audio
sudo systemctl start ffmpeg-combined
sudo systemctl start srt-transmission
```

---

## Stream Processing (Server Side)

The complete server setup now includes:
1. SRT-to-RTSP conversion service (receives from camera)
2. YouTube streaming processing container (processes local RTSP)

### Setup Steps:

1. **Start the SRT-to-RTSP service** (see Server Side section above)
2. **Set up the YouTube streaming container:**

- Place the `youtube-stream` folder on your server.
- Launch the Docker container using `docker-compose` from inside the `youtube-stream` folder.
- The Python script now connects to the local RTSP stream (converted from SRT) and relays it to YouTube.
- The webserver in the container serves hold screens when the main stream is not active.

**To start the container:**

```sh
cd youtube-stream
docker-compose build
docker-compose up -d
```

### More details on youtube-stream setup

- The Python script (`simple-processor.py`) monitors the local RTSP stream at `rtsp://localhost:8554/cam` (converted from the SRT stream).
- If the RTSP stream is unavailable, the script switches to a hold screen (static image or video).
- You can customize hold screens by replacing files in the `overlays` directory inside `youtube-stream`.
- The Docker Compose file (`docker-compose.yml`) defines the service and mounts necessary volumes.
- Custom hold screen images and new stream keys can be added dynamically through the webserver (runs on port 3000).
- Logs and status can be checked with:

```sh
docker logs stream-processor
```

- To update configuration, edit the files and restart the container:

```sh
docker stop stream-processor
docker rm stream-processor
docker-compose build
docker-compose up -d
```
