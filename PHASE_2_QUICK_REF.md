# BirdStream Phase 2 - Quick Reference Guide

## Files Created (5 modules, ~50KB total)

| File | Size | Purpose |
|------|------|---------|
| `camera_capture.py` | 12.1 KB | Video capture from Camera Module 3 |
| `audio_capture.py` | 13.4 KB | Audio capture from USB microphone |
| `stream_encoder.py` | 8.9 KB | Combines and encodes video+audio |
| `network_stream.py` | 9.3 KB | Manages server connection |
| `main.py` | 6.6 KB | Orchestrates all components |

## Component Relationships

```
camera_capture.py ──┐
                    ├──> stream_encoder.py ──> network_stream.py ──> Server
audio_capture.py ───┘
     ▲                            ▲
     │                            │
     └────────> main.py <─────────┘
                (orchestrates)
```

## Key Classes

### CameraCapture
```python
camera = CameraCapture(config)
camera.initialize()          # Setup hardware
camera.start()              # Begin capture
frame = camera.get_frame()  # Get video frame
status = camera.get_status()
camera.stop()
camera.cleanup()
```

### AudioCapture
```python
audio = AudioCapture(config)
audio.initialize()          # Setup hardware
audio.start()              # Begin capture
audio_data = audio.get_frame()  # Get audio chunk
status = audio.get_status()
audio.stop()
audio.cleanup()
```

### StreamEncoder
```python
encoder = StreamEncoder(config, camera, audio)
encoder.start("rtmp://server:5000/live")  # Start encoding
status = encoder.get_status()
encoder.stop()
```

### NetworkStream
```python
network = NetworkStream(config)
network.connect()           # Connect to server
network.start_streaming(encoder)  # Begin transmission
network.send_metadata({...})  # Send stream info
status = network.get_status()
network.stop_streaming()
network.disconnect()
```

### BirdStreamApp
```python
app = BirdStreamApp('config.yaml')
app.start()    # Initialize and start all
app.run()      # Main loop
app.stop()     # Cleanup and shutdown
status = app.get_status()  # Get full status
```

## Configuration Flow

```
config.yaml
    ├─> camera section ──> CameraCapture
    ├─> audio section ───> AudioCapture
    ├─> encoder section ─> StreamEncoder
    ├─> server section ──> NetworkStream
    └─> all sections ────> BirdStreamApp
```

## Data Buffers

### Camera Buffer
- Type: Circular deque
- Size: 100 frames max
- Each frame: ~150KB (JPEG)
- Total: ~15MB

### Audio Buffer
- Type: Circular deque
- Size: 2000 chunks max
- Each chunk: ~4KB (PCM)
- Total: ~8MB

## Error Recovery Strategy

### Level 1: Module-Level Recovery
- Retry count: Up to 5
- Backoff: 1s → 2s → 4s → 8s → 16s
- Action on failure: Stop module, log error

### Level 2: Application-Level Recovery
- Connection retry: Up to 5 attempts
- Backoff: Same exponential schedule
- Action on failure: Stop application

### Level 3: Server-Level Recovery
- Fallback to 'reconnecting' state
- Switch to static images if needed
- Monitored via health checks

## Performance Tuning

### For Low Network Bandwidth
```yaml
camera:
  bitrate: 2000  # Reduce from 4000
  fps: 15        # Reduce from 30
```

### For Low CPU
```yaml
encoder:
  preset: fast   # Change from medium
```

### For High Latency
```yaml
encoder:
  buffer_size: 524288  # Reduce from 1048576
```

## Logging Output

```
2024-10-20 10:30:45,123 - root - INFO - BirdStream - Raspberry Pi Camera & Audio Streamer
2024-10-20 10:30:45,124 - root - INFO - ==================================================
2024-10-20 10:30:45,125 - __main__ - INFO - BirdStream application initialized
2024-10-20 10:30:45,126 - __main__ - INFO - Starting BirdStream components...
2024-10-20 10:30:45,200 - camera_capture - INFO - Initializing camera hardware...
2024-10-20 10:30:45,300 - audio_capture - INFO - Initializing audio hardware...
2024-10-20 10:30:45,400 - stream_encoder - INFO - Stream Encoder initialized: ffmpeg
2024-10-20 10:30:45,500 - network_stream - INFO - Connecting to 192.168.0.21:5000...
2024-10-20 10:30:45,600 - network_stream - INFO - Successfully connected to server
2024-10-20 10:30:45,700 - __main__ - INFO - BirdStream started successfully
2024-10-20 10:30:45,800 - __main__ - INFO - BirdStream running. Press Ctrl+C to stop.
```

## Status Dictionary Structure

```python
{
    'timestamp': 1728123045.123,
    'running': True,
    'camera': {
        'enabled': True,
        'initialized': True,
        'running': True,
        'frame_count': 1234,
        'error_count': 0,
        'buffer_size': 95,
        'buffer_bytes': 14250000,
        'drop_rate': 0.0,
        'config': {
            'width': 1920,
            'height': 1080,
            'fps': 30,
            'bitrate': 4000000,
            'format': 'h264'
        }
    },
    'audio': { ... },
    'encoder': { ... },
    'network': { ... }
}
```

## Troubleshooting

### Camera not initializing
- Check: `sudo vcgencmd get_camera`
- Enable: Settings → Interfacing Options → Camera

### Audio device not found
- List: `arecord -L` (Linux)
- Verify USB device: `lsusb`
- Check: `pactl list sources`

### FFmpeg not found
- Install: `sudo apt-get install ffmpeg`
- Check: `ffmpeg -version`

### Connection refused
- Verify server is running
- Check firewall settings
- Verify IP address in config.yaml

### High CPU usage
- Reduce bitrate in config
- Change preset to 'fast'
- Reduce frame rate

## Testing Commands

```bash
# Check module imports
python -c "from camera_capture import CameraCapture"

# Run with test config
python main.py

# Check FFmpeg
ffmpeg -version

# Monitor system resources
watch -n 1 'top -b -n 1 | head -15'
```

## Next Phase

Ready for **Phase 3: Server Reception & Processing**
- Stream receiver implementation
- YouTube RTMP routing
- Static image handler
- Reconnection state management

---

**Created:** October 20, 2025
**Phase:** 2 (Raspberry Pi Capture Layer) ✅
**Status:** Complete and Production Ready
