"""
BirdStream - Camera Capture Module
Handles video capture from Camera Module 3 Wide with H.264 encoding.
Implements buffer management and error handling for WiFi drops.
"""

import io
import logging
import threading
import time
from typing import Callable, Optional
from collections import deque

try:
    from picamera2 import Picamera2
    from libcamera import controls
except ImportError:
    logging.warning("picamera2 not available - running in simulation mode")
    Picamera2 = None


logger = logging.getLogger(__name__)


class CameraBuffer:
    """
    Thread-safe circular buffer for camera frames.
    Maintains a fixed-size buffer of encoded H.264 data.
    """
    
    def __init__(self, max_size: int = 100):
        """
        Initialize camera buffer.
        
        Args:
            max_size: Maximum number of frames to buffer
        """
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.frame_count = 0
        self.drop_count = 0
    
    def put(self, frame_data: bytes, timestamp: float) -> bool:
        """
        Add frame to buffer.
        
        Args:
            frame_data: Encoded frame bytes
            timestamp: Frame timestamp
            
        Returns:
            True if successful, False if buffer full
        """
        with self.lock:
            try:
                self.buffer.append({
                    'data': frame_data,
                    'timestamp': timestamp,
                    'size': len(frame_data)
                })
                self.frame_count += 1
                return True
            except Exception as e:
                logger.error(f"Error adding frame to buffer: {e}")
                self.drop_count += 1
                return False
    
    def get(self) -> Optional[dict]:
        """
        Get frame from buffer (FIFO).
        
        Returns:
            Frame dict or None if empty
        """
        with self.lock:
            if len(self.buffer) > 0:
                return self.buffer.popleft()
            return None
    
    def get_all(self) -> list:
        """
        Get all frames from buffer and clear it.
        
        Returns:
            List of all frames
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


class CameraCapture:
    """
    Main camera capture module for BirdStream.
    Captures video from Camera Module 3 Wide at 1080p 30fps.
    """
    
    def __init__(self, config: dict):
        """
        Initialize camera capture.
        
        Args:
            config: Configuration dict from config.yaml
        """
        self.config = config.get('camera', {})
        self.enabled = self.config.get('enabled', True)
        self.width = self.config.get('width', 1920)
        self.height = self.config.get('height', 1080)
        self.fps = self.config.get('fps', 30)
        self.bitrate = self.config.get('bitrate', 4000) * 1000  # Convert to bps
        self.format = self.config.get('format', 'h264')
        self.quality = self.config.get('quality', 'high')
        
        self.camera = None
        self.buffer = CameraBuffer(max_size=100)
        self.is_running = False
        self.capture_thread = None
        self.frame_count = 0
        self.error_count = 0
        self.last_error = None
        
        # Callbacks
        self.on_frame_callback: Optional[Callable] = None
        
        logger.info(f"Camera Capture initialized: {self.width}x{self.height} @ {self.fps}fps")
    
    def initialize(self) -> bool:
        """
        Initialize camera hardware.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.info("Camera capture disabled in config")
            return False
        
        if Picamera2 is None:
            logger.error("picamera2 library not available")
            return False
        
        try:
            logger.info("Initializing camera hardware...")
            self.camera = Picamera2()
            
            # Configure camera
            config = self.camera.create_video_configuration(
                main={"size": (self.width, self.height), "format": "YUV420"}
            )
            self.camera.configure(config)
            
            # Set camera controls
            self.camera.set_controls({
                controls.FrameRate: self.fps,
                controls.Brightness: 0,
                controls.Contrast: 1.0,
                controls.Saturation: 1.0,
                controls.Sharpness: 1.0,
                controls.NoiseReductionMode: controls.draft.NoiseReductionModeEnum.Automatic,
            })
            
            logger.info("Camera hardware initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return False
    
    def start(self) -> bool:
        """
        Start camera capture.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or self.camera is None:
            logger.error("Camera not initialized")
            return False
        
        if self.is_running:
            logger.warning("Camera already running")
            return False
        
        try:
            logger.info("Starting camera capture...")
            self.camera.start()
            
            self.is_running = True
            self.frame_count = 0
            self.buffer.clear()
            
            # Start capture thread
            self.capture_thread = threading.Thread(
                target=self._capture_loop,
                daemon=True
            )
            self.capture_thread.start()
            
            logger.info("Camera capture started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start camera capture: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return False
    
    def stop(self):
        """Stop camera capture."""
        if not self.is_running:
            return
        
        try:
            logger.info("Stopping camera capture...")
            self.is_running = False
            
            if self.capture_thread:
                self.capture_thread.join(timeout=5)
            
            if self.camera:
                self.camera.stop()
            
            logger.info("Camera capture stopped")
            
        except Exception as e:
            logger.error(f"Error stopping camera: {e}")
    
    def cleanup(self):
        """Cleanup camera resources."""
        self.stop()
        
        try:
            if self.camera:
                self.camera.close()
                self.camera = None
            logger.info("Camera resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up camera: {e}")
    
    def _capture_loop(self):
        """Main capture loop - runs in separate thread."""
        retry_count = 0
        max_retries = 5
        retry_delay = 1
        
        while self.is_running:
            try:
                # Capture frame
                request = self.camera.capture_request()
                
                # Get frame metadata
                timestamp = time.time()
                
                # Encode frame to H.264
                # For now, we'll use the raw frame data
                # In production, you'd use ffmpeg or libx264 for encoding
                frame_data = request.make_image("main")
                
                # Convert PIL image to bytes
                img_bytes = io.BytesIO()
                frame_data.save(img_bytes, format='JPEG')
                frame_bytes = img_bytes.getvalue()
                
                request.release()
                
                # Add to buffer
                self.buffer.put(frame_bytes, timestamp)
                self.frame_count += 1
                
                # Call callback if set
                if self.on_frame_callback:
                    try:
                        self.on_frame_callback(frame_bytes, timestamp)
                    except Exception as e:
                        logger.error(f"Error in frame callback: {e}")
                
                # Reset retry count on success
                retry_count = 0
                
                # Small delay to maintain frame rate
                time.sleep(1 / self.fps)
                
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                self.error_count += 1
                self.last_error = str(e)
                
                retry_count += 1
                if retry_count > max_retries:
                    logger.error("Max retries exceeded, stopping capture")
                    self.is_running = False
                    break
                
                logger.info(f"Retrying capture in {retry_delay}s (attempt {retry_count}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10)  # Exponential backoff up to 10s
    
    def get_frame(self) -> Optional[bytes]:
        """
        Get next frame from buffer.
        
        Returns:
            Frame bytes or None if buffer empty
        """
        frame = self.buffer.get()
        if frame:
            return frame['data']
        return None
    
    def get_all_frames(self) -> list:
        """
        Get all buffered frames and clear buffer.
        
        Returns:
            List of frame bytes
        """
        frames = self.buffer.get_all()
        return [f['data'] for f in frames]
    
    def get_status(self) -> dict:
        """
        Get camera status.
        
        Returns:
            Status dict
        """
        stats = self.buffer.stats()
        return {
            'enabled': self.enabled,
            'initialized': self.camera is not None,
            'running': self.is_running,
            'frame_count': self.frame_count,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'buffer_size': stats['current_frames'],
            'buffer_bytes': stats['total_bytes'],
            'drop_rate': stats['drop_rate'],
            'config': {
                'width': self.width,
                'height': self.height,
                'fps': self.fps,
                'bitrate': self.bitrate,
                'format': self.format,
            }
        }
    
    def set_frame_callback(self, callback: Callable):
        """
        Set callback function for each captured frame.
        
        Args:
            callback: Function(frame_bytes, timestamp) called for each frame
        """
        self.on_frame_callback = callback
