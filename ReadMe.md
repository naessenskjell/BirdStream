# BirdStream - Camera to Server Streaming System

## Architecture Overview

This system streams video from a Raspberry Pi camera to a remote server using RTMP protocol with a buffer for robust transmission over unreliable networks.

**Flow:**
1. **Camera (Raspberry Pi)**: Captures video/audio → Local RTSP streams → Combined stream → RTMP transmission to server
2. **Server**: Receives RTMP stream → YouTube streaming processor

On the camera side, two separate streams get created, one for the video and one for the audio. These then get combined into a single stream and transmitted to the server over RTMP.

## Hardware

- Raspberry Pi 3B+
- Camera Module 3 Wide
- USB Microphone (mono input, converted to stereo)
- Power supply, fan, ...

## Setting up the camera

### 1. Setting up MediaMTX

MediaMTX acts as a robust RTSP server on the Raspberry Pi to manage local streams before RTMP transmission.

#### 1. Install MediaMTX

```sh
wget https://github.com/bluenviron/mediamtx/releases/latest/download/mediamtx_linux_armv7.tar.gz
tar xvf mediamtx_linux_armv7.tar.gz
sudo mv mediamtx /usr/local/bin/
```

#### 2. Configure MediaMTX

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

#### 3. Start MediaMTX

```sh
./mediamtx /path/to/mediamtx.yml
```

#### 4. Autostart MediaMTX

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

### 2. Autostarting Camera Streams with systemd

To automatically start the camera streaming pipeline on boot, create the following systemd service files on the Raspberry Pi.

#### 1. Video Stream Service

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

#### 2. Audio Stream Service (with Mono to Stereo Conversion)

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

#### 3. Combined Stream Service

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

#### 4. Combined Stream Transmission Service

```ini
[Unit]
Description=Stream Transmission to Server
After=network.target ffmpeg-combined.service

[Service]
ExecStart=/bin/bash -c 'ffmpeg -rtsp_transport tcp -i rtsp://localhost:8554/cam -c:v copy -c:a aac -b:a 96k -f flv rtmp://YOUR_SERVER_IP/live/stream
Restart=always
RestartSec=5
User=admin

[Install]
WantedBy=multi-user.target
```

Replace `YOUR_SERVER_IP` with your server's IP address. Save as `/etc/systemd/system/stream-transmission.service`.


#### 5. Enable and Start Services (Camera Side)

```sh
sudo systemctl enable mediamtx
sudo systemctl enable ffmpeg-video
sudo systemctl enable ffmpeg-audio
sudo systemctl enable ffmpeg-combined
sudo systemctl enable stream-transmission

sudo systemctl start mediamtx
sudo systemctl start ffmpeg-video
sudo systemctl start ffmpeg-audio
sudo systemctl start ffmpeg-combined
sudo systemctl start stream-transmission
```

---

## Setting up the Server

### 1. Receive Stream Using Nginx

On the server, receive the stream from the camera and host it locally:

Add the following in `/etc/nginx/nginx.conf`:

```ini
rtmp {
    server {
        listen 1935;
        chunk_size 4096;

        application live {
            live on;
            record off;

            # HLS settings
            hls on;
            hls_path /tmp/hls;
            hls_fragment 10s;
            hls_playlist_length 30s;
            hls_continuous on;
            hls_cleanup on;
        }
    }
}
```

This makes Nginx listen on port 1935 for RTMP on the /live application. In this case, a 30 second buffer is added for stability.

Restart the service:

```sh
sudo systemctl reload nginx
```

### 2. Stream Processing

Launch the YouTube streaming processing container (processes local RTSP)

#### Setup Steps:

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

- The Python script (`simple-processor.py`) monitors the local RTSP stream at `rtsp://localhost:8554/live/stream`.
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
