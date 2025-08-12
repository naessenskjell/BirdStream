# Camera

## Hardware

- Raspberry Pi 3B+
- Camera Module 3 Wide
- Power supply, fan, ...

## Video Streaming

You can stream the camera feed via RTSP using `rpicam-vid` and `ffmpeg`, with MediaMTX as the RTSP server. This works for both silent and real audio.

---

## Setting up MediaMTX

MediaMTX acts as a robust RTSP server to relay your stream to clients.

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

## Streaming with Silent Audio

Some players require an audio track in the RTSP stream. If you do not have a microphone connected, you can add a silent audio track using `ffmpeg` and `rpicam-vid`.

### 1. Install ffmpeg and rpicam-apps

```sh
sudo apt update
sudo apt install ffmpeg
sudo apt install rpicam-apps
```

### 2. Start Streaming with Silent Audio

Use `rpicam-vid` to capture video and pipe it to `ffmpeg`, which adds a silent audio track and streams to MediaMTX:

```sh
rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o - \
| ffmpeg -thread_queue_size 512 -re -i - \
-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
-c:v copy -c:a aac -ar 44100 -b:a 128k \
-f rtsp rtsp://localhost:8554/stream
```

- `rpicam-vid ... -o -`: Capture H.264 video from the Pi camera and output to stdout.
- `ffmpeg -re -i -`: Read video from stdin.
- `-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100`: Generate silent audio.
- `-c:v copy`: Copy video without re-encoding.
- `-c:a aac -ar 44100 -b:a 128k`: Encode audio as AAC.
- `-f rtsp rtsp://localhost:8554/stream`: ffmpeg serves RTSP to MediaMTX.

### 3. Autostart the ffmpeg/rpicam-vid Stream

To ensure the stream starts automatically on boot, create a systemd service:

```sh
sudo nano /etc/systemd/system/ffmpeg-rtsp.service
```

Use the following service file:

```ini
[Unit]
Description=FFmpeg RTSP Stream with Silent Audio (rpicam-vid)
After=network.target

[Service]
ExecStart=/bin/bash -c 'rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o - | ffmpeg -thread_queue_size 512 -re -i - -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -c:v copy -c:a aac -ar 44100 -b:a 128k -f rtsp rtsp://localhost:8554/stream'
Restart=always
RestartSec=5
User=admin

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```sh
sudo systemctl enable ffmpeg-rtsp
sudo systemctl start ffmpeg-rtsp
```

---

## Streaming with a Connected Microphone

If you connect a microphone to your Raspberry Pi, you can stream both video and real audio.

### 1. List Audio Devices

```sh
arecord -l
```

Look for your microphone's card and device number.

### 2. Start Streaming with Real Audio

Replace `hw:1,0` with your actual device if different:

```sh
rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o - | \
ffmpeg -thread_queue_size 512 -re -i - \
  -f alsa -i hw:1,0 \
  -c:v copy -c:a aac -ar 44100 -b:a 128k \
  -f rtsp rtsp://localhost:8554/stream
```

- `-f alsa -i hw:1,0`: Capture audio from the microphone.

### 3. Autostart the ffmpeg/rpicam-vid Stream with Microphone

If you are using a microphone, update the service file:

```sh
sudo nano /etc/systemd/system/ffmpeg-rtsp.service
```

Replace the `ExecStart` line with:

```ini
ExecStart=/bin/bash -c 'rpicam-vid -t 0 --inline --width 1920 --height 1080 --framerate 30 -o - | ffmpeg -thread_queue_size 512 -re -i - -f alsa -i hw:1,0 -c:v copy -c:a aac -ar 44100 -b:a 128k -f rtsp rtsp://localhost:8554/stream'
```

Enable and start the service (if not already done):

```sh
sudo systemctl enable ffmpeg-rtsp
sudo systemctl start ffmpeg-rtsp
```

Now, clients can connect to `rtsp://<raspberrypi-ip>:8554/cam` via MediaMTX.