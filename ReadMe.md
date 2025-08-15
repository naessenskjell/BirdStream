# Camera

## Hardware

- Raspberry Pi 3B+
- Camera Module 3 Wide
- Power supply, fan, ...

## Main Streaming Workflow: Separate Video and Audio RTSP Streams

For robust and flexible streaming, transmit video and audio as separate RTSP streams and combine them into a unified stream for downstream processing or viewing.

### 1. Stream Video Only

```sh
rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o - \
| ffmpeg -nostdin -thread_queue_size 512 -fflags +genpts -re -i - \
  -c:v copy -an \
  -f rtsp rtsp://localhost:8554/video
```

- `-an`: disables audio in the video stream.

### 2. Stream Audio Only

```sh
ffmpeg -nostdin -f alsa -channels 1 -ar 44100 -i hw:1,0 \
  -af "volume=2.0" \
  -c:a aac -ar 44100 -b:a 128k \
  -vn \
  -f rtsp rtsp://localhost:8554/audio
```

- `-vn`: disables video in the audio stream.

### 3. Combine Video and Audio Streams

Use ffmpeg to merge the separate RTSP streams into a single stream for clients or further processing:

```sh
ffmpeg -i rtsp://localhost:8554/video -i rtsp://localhost:8554/audio \
  -c:v copy -c:a copy \
  -f rtsp rtsp://localhost:8554/stream
```

- This unified stream can be relayed by MediaMTX or consumed by downstream services.

**Why separate streams?**

- Isolates video and audio pipelines for easier troubleshooting and flexibility.
- Allows independent restarts and monitoring.
- Can help avoid audio dropouts or sync issues caused by hardware or software bugs.

---

## Setting up MediaMTX

MediaMTX acts as a robust RTSP server to relay your streams to clients.

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
  cam:
    source: rtsp://localhost:8554/stream
```

`cam` combines `video` and `audio` as a single stream.

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

Enable and start the service:

```sh
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
```

---

## Autostarting ffmpeg Streams with systemd

To automatically start the separate video, audio, and combined streams on boot, create the following systemd service files.

### 1. Video Stream Service

```ini
[Unit]
Description=FFmpeg RTSP Video Stream
After=network.target

[Service]
ExecStart=/bin/bash -c 'rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o - | ffmpeg -nostdin -thread_queue_size 512 -fflags +genpts -re -i - -c:v copy -an -f rtsp rtsp://localhost:8554/video'
Restart=always
RestartSec=5
User=admin

[Install]
WantedBy=multi-user.target
```

Save as `/etc/systemd/system/ffmpeg-video.service`.

### 2. Audio Stream Service

```ini
[Unit]
Description=FFmpeg RTSP Audio Stream
After=network.target

[Service]
ExecStart=/bin/bash -c 'ffmpeg -nostdin -f alsa -channels 1 -ar 44100 -i hw:1,0 -af "volume=2.0" -c:a aac -ar 44100 -b:a 128k -vn -f rtsp rtsp://localhost:8554/audio'
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
After=network.target

[Service]
ExecStart=/bin/bash -c 'ffmpeg -i rtsp://localhost:8554/video -i rtsp://localhost:8554/audio -c:v copy -c:a copy -f rtsp rtsp://localhost:8554/stream'
Restart=always
RestartSec=5
User=admin

[Install]
WantedBy=multi-user.target
```

Save as `/etc/systemd/system/ffmpeg-combined.service`.

### Enable and Start Services

```sh
sudo systemctl enable ffmpeg-video
sudo systemctl enable ffmpeg-audio
sudo systemctl enable ffmpeg-combined

sudo systemctl start ffmpeg-video
sudo systemctl start ffmpeg-audio
sudo systemctl start ffmpeg-combined
```

---

## Stream processing

Basic setup on the server:

- Place the `youtube-stream` folder on your server.
- Launch the Docker container using `docker-compose` from inside the `youtube-stream` folder.
- This will run the Python script that redirects the RTSP stream to YouTube.
- The webserver in the container can serve hold screens, which are shown on YouTube when the main stream is not active.

**To start the container:**

```sh
cd youtube-stream
docker-compose build
docker-compose up -d
```

### More details on youtube-stream setup

- The Python script (`main.py`) inside the container monitors the RTSP stream and relays it to YouTube using ffmpeg.
- If the RTSP stream is unavailable, the script switches to a hold screen (static image or video) served from the webserver.
- You can customize hold screens by replacing files in the `hold_screens` directory inside `youtube-stream`.
- Configuration (such as YouTube stream key, RTSP source, and hold screen paths) is set in the `config.yaml` file.
- The Docker Compose file (`docker-compose.yml`) defines the service and mounts necessary volumes for configuration and hold screens.
- Custom hold screen images and new stream keys can be added dynamically through the webserver (that runs on port 3000).
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

## Troubleshooting: Mono Microphone Audio Dropouts

If your audio stream works on boot but drops out after some time:

- **Test microphone stability:**  
  Run `arecord -D hw:1,0 -f S16_LE -c1 -r 44100 test.wav` and play back with `aplay test.wav` to check if the device disconnects or fails.
- **Check system logs:**  
  Run `journalctl -u ffmpeg-rtsp` and `dmesg` for hardware or ALSA errors.
- **Try a different USB port or power supply** for the microphone.
- **Update Raspberry Pi OS and firmware:**  
  `sudo apt update && sudo apt upgrade && sudo rpi-update`
- **Try a different microphone** to rule out hardware issues.
- **Increase ALSA buffer size:**  
  Add `-buffer_size 512k` to the ffmpeg ALSA input if supported.
- **Restart the service:**  
  `sudo systemctl restart ffmpeg-rtsp`
- **Check for suspend/power-saving:**  
  Disable USB autosuspend if needed.

If issues persist, consider using a USB sound card or a different microphone model.