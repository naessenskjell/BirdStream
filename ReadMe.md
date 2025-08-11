# Camera

## Hardware

- Raspberry Pi 3B+
- Camera Module 3 Wide
- Power supply, fan, ...

## Video Streaming without audio

The Pi runs a MediaMTX server and streams the camera feed via RTSP. Setup is very simple:

### 1. Install MediaMTX

```sh
wget https://github.com/bluenviron/mediamtx/releases/latest/download/mediamtx_linux_armv7.tar.gz
tar xvf mediamtx_linux_armv7.tar.gz
sudo mv mediamtx /usr/local/bin/
```

### 2. Configure MediaMTX

Edit your `mediamtx.yml`:

```yaml
...
paths:
  cam:
    source: rpiCamera
    rpiCameraWidth: 1920
    rpiCameraHeight: 1080
    rpiCameraFps: 30
    rpiCameraBitrate: 8000000

  # example:
  # my_camera:
  #   source: rtsp://my_camera

  # Settings under path "all_others" are applied to all paths that
  # do not match another entry.
  all_others:
...
```

### 3. Start Streaming

```sh
mediamtx
```

### 4. Autostart

Create a systemd service file:

```sh
sudo nano /etc/systemd/system/mediamtx.service
```

Place the following inside:

```ini
[Unit]
Description=MediaMTX RTSP Server
After=network.target

[Service]
ExecStart=/usr/local/bin/mediamtx /path/to/mediamtx.yml
Restart=always
User=pi
Group=video

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```sh
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
```


## Adding a Silent Audio Track

Some players require an audio track in the RTSP stream. If you do not have a microphone connected, you can add a silent audio track using `ffmpeg`.

### 1. Install ffmpeg

```sh
sudo apt update
sudo apt install ffmpeg
```

### 2. Start Streaming with Silent Audio

Use `ffmpeg` to combine the camera video with a silent audio track and stream it to MediaMTX:

```sh
ffmpeg -f v4l2 -i /dev/video0 -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
-c:v copy -c:a aac -f rtsp rtsp://localhost:8554/cam
```

- `-f v4l2 -i /dev/video0`: Capture video from the camera.
- `-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100`: Generate silent audio.
- `-c:v copy`: Copy video without re-encoding.
- `-c:a aac`: Encode audio as AAC.
- `-f rtsp rtsp://localhost:8554/cam`: Output as RTSP to MediaMTX.

### 3. Configure MediaMTX

Edit your `mediamtx.yml` to use the RTSP stream from ffmpeg as the source:

```yaml
paths:
  cam:
    source: rtsp://localhost:8554/cam
```

Now, your RTSP stream will include a silent audio track.

### 4. Autostart the ffmpeg Stream

To ensure the ffmpeg stream starts automatically on boot, create a systemd service:

```sh
sudo nano /etc/systemd/system/ffmpeg-rtsp.service
```

For silent audio, use the following service file:

```ini
[Unit]
Description=FFmpeg RTSP Stream with Silent Audio
After=network.target

[Service]
ExecStart=/usr/bin/ffmpeg -f v4l2 -i /dev/video0 -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -c:v copy -c:a aac -f rtsp rtsp://localhost:8554/cam
Restart=always
User=pi

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

If you connect a microphone to your Raspberry Pi, you can stream both video and real audio. First, identify your microphone device (often `/dev/snd/` or `hw:1,0`).

### 1. List Audio Devices

```sh
arecord -l
```

Look for your microphone's card and device number.

### 2. Start Streaming with Real Audio

Replace `hw:1,0` with your actual device if different:

```sh
ffmpeg -f v4l2 -i /dev/video0 -f alsa -i hw:1,0 \
-c:v copy -c:a aac -f rtsp rtsp://localhost:8554/cam
```

- `-f alsa -i hw:1,0`: Capture audio from the microphone.

### 3. Configure MediaMTX

Edit your `mediamtx.yml` as before:

```yaml
paths:
  cam:
    source: rtsp://localhost:8554/cam
```

Now, your RTSP stream will include real audio from the microphone.

### 4. Autostart the ffmpeg Stream with Microphone

If you are using a microphone, update the service file:

```sh
sudo nano /etc/systemd/system/ffmpeg-rtsp.service
```

Replace the `ExecStart` line with:

```ini
ExecStart=/usr/bin/ffmpeg -f v4l2 -i /dev/video0 -f alsa -i hw:1,0 -c:v copy -c:a aac -f rtsp rtsp://localhost:8554/cam
```

Enable and start the service (if not already done):

```sh
sudo systemctl enable ffmpeg-rtsp
sudo systemctl start ffmpeg-rtsp
```

Now, the ffmpeg stream will autostart with your chosen audio source.