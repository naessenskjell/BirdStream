"""
BirdStream - Audio Capture Module
Handles audio capture from USB Microphone with sync and low-latency processing.
"""

import logging
import threading
import time
from typing import Callable, Optional
from collections import deque

try:
    import pyaudio
    import numpy as np
except ImportError:
    logging.warning("pyaudio/numpy not available - running in simulation mode")
    pyaudio = None
    np = None


logger = logging.getLogger(__name__)


class AudioBuffer:
    """
    Thread-safe circular buffer for audio frames.
    Maintains a fixed-size buffer of audio data.
    """
    
    def __init__(self, max_frames: int = 1000):
        """
        Initialize audio buffer.
        
        Args:
            max_frames: Maximum number of frames to buffer
        """
        self.buffer = deque(maxlen=max_frames)
        self.lock = threading.Lock()
        self.frame_count = 0
        self.drop_count = 0
    
    def put(self, audio_data: bytes, timestamp: float) -> bool:
        """
        Add audio frame to buffer.
        
        Args:
            audio_data: Raw audio bytes
            timestamp: Frame timestamp
            
        Returns:
            True if successful, False if buffer full
        """
        with self.lock:
            try:
                self.buffer.append({
                    'data': audio_data,
                    'timestamp': timestamp,
                    'size': len(audio_data)
                })
                self.frame_count += 1
                return True
            except Exception as e:
                logger.error(f"Error adding audio frame to buffer: {e}")
                self.drop_count += 1
                return False
    
    def get(self) -> Optional[dict]:
        """
        Get audio frame from buffer (FIFO).
        
        Returns:
            Audio frame dict or None if empty
        """
        with self.lock:
            if len(self.buffer) > 0:
                return self.buffer.popleft()
            return None
    
    def get_all(self) -> list:
        """
        Get all audio frames from buffer and clear it.
        
        Returns:
            List of all audio frames
        """
        with self.lock:
            frames = list(self.buffer)
            self.buffer.clear()
            return frames
    
    def size(self) -> int:
        """Get current buffer size."""
        with self.lock:
            return len(self.buffer)
    
    def stats(self) -> dict:
        """Get buffer statistics."""
        with self.lock:
            total_bytes = sum(f['size'] for f in self.buffer)
            return {
                'current_frames': len(self.buffer),
                'total_bytes': total_bytes,
                'frame_count': self.frame_count,
                'drop_count': self.drop_count,
                'drop_rate': self.drop_count / max(1, self.frame_count)
            }
    
    def clear(self):
        """Clear buffer."""
        with self.lock:
            self.buffer.clear()


class AudioCapture:
    """
    Main audio capture module for BirdStream.
    Captures audio from USB Microphone with low-latency processing.
    """
    
    def __init__(self, config: dict):
        """
        Initialize audio capture.
        
        Args:
            config: Configuration dict from config.yaml
        """
        self.config = config.get('audio', {})
        self.enabled = self.config.get('enabled', True)
        self.device_name = self.config.get('device', 'default')
        self.sample_rate = self.config.get('sample_rate', 48000)
        self.channels = self.config.get('channels', 1)
        self.bitrate = self.config.get('bitrate', 128) * 1000  # Convert to bps
        self.format = self.config.get('format', 'aac')
        
        # PyAudio constants
        self.CHUNK_SIZE = 2048  # Frames per buffer
        # Use the PyAudio constant when available; fallback to numeric value
        self.AUDIO_FORMAT = pyaudio.paInt16 if pyaudio is not None else 2  # paInt16 (16-bit)
        self.SAMPLE_WIDTH = 2  # Bytes per sample
        
        self.audio = None
        self.stream = None
        self.device_index = None
        self.buffer = AudioBuffer(max_frames=2000)
        self.is_running = False
        self.capture_thread = None
        self.frame_count = 0
        self.error_count = 0
        self.last_error = None
        
        # Callbacks
        self.on_frame_callback: Optional[Callable] = None
        
        logger.info(f"Audio Capture initialized: {self.sample_rate}Hz, {self.channels}ch, {self.format}")
    
    def find_device(self) -> Optional[int]:
        """
        Find audio device by name or default.
        
        Returns:
            Device index or None if not found
        """
        if pyaudio is None:
            logger.error("PyAudio not available")
            return None

        try:
            p = pyaudio.PyAudio()
            device_count = p.get_device_count()

            logger.info(f"Found {device_count} audio devices")

            # If looking for default, try PyAudio's default first
            if self.device_name == 'default':
                try:
                    default_info = p.get_default_input_device_info()
                    idx = default_info.get('index')
                    logger.info(f"Using default audio device: index {idx}")
                    p.terminate()
                    return idx
                except Exception:
                    # Fall through to picking the first available input-capable device
                    logger.warning("No PyAudio default input device available, enumerating devices")

            # Search for device by name if specified
            if self.device_name != 'default':
                for i in range(device_count):
                    info = p.get_device_info_by_index(i)
                    if self.device_name.lower() in info.get('name', '').lower():
                        logger.info(f"Found device '{info['name']}' at index {i}")
                        p.terminate()
                        return i

            # If we get here, pick the first device that supports input
            for i in range(device_count):
                try:
                    info = p.get_device_info_by_index(i)
                    if int(info.get('maxInputChannels', 0)) > 0:
                        logger.info(f"Selecting input-capable device '{info.get('name')}' at index {i}")
                        p.terminate()
                        return i
                except Exception:
                    continue

            logger.error("No input-capable audio device found")
            p.terminate()
            return None

        except Exception as e:
            logger.error(f"Error finding audio device: {e}")
            return None
    
    def initialize(self) -> bool:
        """
        Initialize audio capture hardware.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.info("Audio capture disabled in config")
            return False
        
        if pyaudio is None:
            logger.error("PyAudio library not available")
            return False
        
        try:
            logger.info("Initializing audio hardware...")

            # Find device
            self.device_index = self.find_device()
            if self.device_index is None:
                logger.error("No audio device index found during initialization")
                return False

            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()

            # Probe supported sample rates for the chosen device and select one that works
            try:
                info = self.audio.get_device_info_by_index(self.device_index)
                device_default_rate = int(info.get('defaultSampleRate', 0))
            except Exception:
                device_default_rate = 0

            tried_rates = []
            # Candidate rates: configured, device default, common rates
            candidates = [self.sample_rate]
            if device_default_rate and device_default_rate not in candidates:
                candidates.append(device_default_rate)
            for r in (48000, 44100):
                if r not in candidates:
                    candidates.append(r)

            selected_rate = None
            for rate in candidates:
                if rate in tried_rates:
                    continue
                tried_rates.append(rate)
                try:
                    supported = self.audio.is_format_supported(
                        rate,
                        input_device=self.device_index,
                        input_channels=self.channels,
                        input_format=self.AUDIO_FORMAT
                    )
                    if supported:
                        selected_rate = rate
                        logger.info(f"Audio device {self.device_index} supports rate {rate}")
                        break
                except Exception as e:
                    logger.debug(f"Rate {rate} not supported for device {self.device_index}: {e}")

            if selected_rate is None:
                logger.error(f"None of the candidate sample rates are supported on device {self.device_index}: {candidates}")
                return False

            # Apply selected rate
            if selected_rate != self.sample_rate:
                logger.warning(f"Configured sample_rate {self.sample_rate} not supported; switching to {selected_rate}")
                self.sample_rate = selected_rate

            logger.info("Audio hardware initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize audio: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return False
    
    def start(self) -> bool:
        """
        Start audio capture.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or self.audio is None:
            logger.error("Audio not initialized")
            return False
        
        if self.is_running:
            logger.warning("Audio capture already running")
            return False
        
        try:
            logger.info(f"Starting audio capture from device {self.device_index}...")
            
            # Open audio stream
            self.stream = self.audio.open(
                format=self.AUDIO_FORMAT,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.CHUNK_SIZE
            )
            
            self.is_running = True
            self.frame_count = 0
            self.buffer.clear()
            
            # Start capture thread
            self.capture_thread = threading.Thread(
                target=self._capture_loop,
                daemon=True
            )
            self.capture_thread.start()
            
            logger.info("Audio capture started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return False
    
    def stop(self):
        """Stop audio capture."""
        if not self.is_running:
            return
        
        try:
            logger.info("Stopping audio capture...")
            self.is_running = False
            
            if self.capture_thread:
                self.capture_thread.join(timeout=5)
            
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            
            logger.info("Audio capture stopped")
            
        except Exception as e:
            logger.error(f"Error stopping audio: {e}")
    
    def cleanup(self):
        """Cleanup audio resources."""
        self.stop()
        
        try:
            if self.audio:
                self.audio.terminate()
                self.audio = None
            logger.info("Audio resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up audio: {e}")
    
    def _capture_loop(self):
        """Main capture loop - runs in separate thread."""
        retry_count = 0
        max_retries = 5
        retry_delay = 1
        
        while self.is_running:
            try:
                # Read audio chunk from stream
                audio_data = self.stream.read(
                    self.CHUNK_SIZE,
                    exception_on_overflow=False
                )
                
                timestamp = time.time()
                
                # Add to buffer
                self.buffer.put(audio_data, timestamp)
                self.frame_count += 1
                
                # Call callback if set
                if self.on_frame_callback:
                    try:
                        self.on_frame_callback(audio_data, timestamp)
                    except Exception as e:
                        logger.error(f"Error in audio callback: {e}")
                
                # Reset retry count on success
                retry_count = 0
                
            except Exception as e:
                logger.error(f"Error in audio capture loop: {e}")
                self.error_count += 1
                self.last_error = str(e)
                
                retry_count += 1
                if retry_count > max_retries:
                    logger.error("Max retries exceeded, stopping audio capture")
                    self.is_running = False
                    break
                
                logger.info(f"Retrying audio capture in {retry_delay}s (attempt {retry_count}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10)  # Exponential backoff
    
    def get_frame(self) -> Optional[bytes]:
        """
        Get next audio frame from buffer.
        
        Returns:
            Audio bytes or None if buffer empty
        """
        frame = self.buffer.get()
        if frame:
            return frame['data']
        return None
    
    def get_all_frames(self) -> list:
        """
        Get all buffered audio frames and clear buffer.
        
        Returns:
            List of audio bytes
        """
        frames = self.buffer.get_all()
        return [f['data'] for f in frames]
    
    def get_status(self) -> dict:
        """
        Get audio status.
        
        Returns:
            Status dict
        """
        stats = self.buffer.stats()
        return {
            'enabled': self.enabled,
            'initialized': self.audio is not None,
            'running': self.is_running,
            'device_index': self.device_index,
            'frame_count': self.frame_count,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'buffer_size': stats['current_frames'],
            'buffer_bytes': stats['total_bytes'],
            'drop_rate': stats['drop_rate'],
            'config': {
                'device': self.device_name,
                'sample_rate': self.sample_rate,
                'channels': self.channels,
                'bitrate': self.bitrate,
                'format': self.format,
            }
        }
    
    def set_frame_callback(self, callback: Callable):
        """
        Set callback function for each captured audio frame.
        
        Args:
            callback: Function(audio_bytes, timestamp) called for each frame
        """
        self.on_frame_callback = callback
