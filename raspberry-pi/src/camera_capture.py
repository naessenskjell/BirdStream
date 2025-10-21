"""
BirdStream - Camera Capture Module
Handles video capture from Camera Module 3 Wide with H.264 encoding.
Implements buffer management and error handling for WiFi drops.
Supports both picamera2 (native Python) and rpicam-vid (command-line fallback).
"""

import io
import logging
import threading
import time
import subprocess
import select
from typing import Callable, Optional
from collections import deque

# Try picamera2 first
try:
    from picamera2 import Picamera2
    from libcamera import controls
    PICAMERA2_AVAILABLE = True
except ImportError:
    logging.warning("picamera2 not available - will use rpicam-vid fallback")
    Picamera2 = None
    PICAMERA2_AVAILABLE = False


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
        self.camera_type = None  # 'picamera2' or 'rpicam-vid'
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
        Tries picamera2 first, falls back to rpicam-vid if not available.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.info("Camera capture disabled in config")
            return False
        
        # Try picamera2 first
        if PICAMERA2_AVAILABLE:
            if self._initialize_picamera2():
                return True
            logger.warning("picamera2 initialization failed, trying rpicam-vid fallback")
        
        # Fall back to rpicam-vid
        if self._initialize_rpicam():
            return True
        
        logger.error("Both picamera2 and rpicam-vid initialization failed")
        return False
    
    def _initialize_picamera2(self) -> bool:
        """Initialize using picamera2."""
        try:
            logger.info("Initializing camera with picamera2...")
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
            
            self.camera_type = 'picamera2'
            logger.info("Camera initialized successfully with picamera2")
            return True
            
        except Exception as e:
            logger.error(f"picamera2 initialization failed: {e}")
            self.camera = None
            return False
    
    def _initialize_rpicam(self) -> bool:
        """Initialize using rpicam-vid command."""
        try:
            # Check if rpicam-vid is available
            result = subprocess.run(['which', 'rpicam-vid'], capture_output=True)
            if result.returncode != 0:
                logger.error("rpicam-vid not found - ensure it's installed")
                return False
            
            logger.info("Using rpicam-vid for camera capture")
            self.camera_type = 'rpicam-vid'
            return True
            
        except Exception as e:
            logger.error(f"rpicam-vid initialization failed: {e}")
            return False
    
    def start(self) -> bool:
        """
        Start camera capture.
        Handles both picamera2 and rpicam-vid modes.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.error("Camera not enabled")
            return False
        
        if self.is_running:
            logger.warning("Camera already running")
            return False
        
        try:
            if self.camera_type == 'picamera2':
                return self._start_picamera2()
            elif self.camera_type == 'rpicam-vid':
                return self._start_rpicam()
            else:
                logger.error(f"Unknown camera type: {self.camera_type}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start camera capture: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return False
    
    def _start_picamera2(self) -> bool:
        """Start picamera2 capture."""
        if self.camera is None:
            logger.error("Camera not initialized")
            return False
        
        try:
            logger.info("Starting camera capture (picamera2)...")
            self.camera.start()
            
            self.is_running = True
            self.frame_count = 0
            self.buffer.clear()
            
            # Start capture thread
            self.capture_thread = threading.Thread(
                target=self._capture_loop_picamera2,
                daemon=True
            )
            self.capture_thread.start()
            
            logger.info("Camera capture started (picamera2)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start picamera2: {e}")
            return False
    
    def _start_rpicam(self) -> bool:
        """Start rpicam-vid capture."""
        try:
            logger.info("Starting camera capture (rpicam-vid)...")
            
            self.is_running = True
            self.frame_count = 0
            self.buffer.clear()
            
            # Start capture thread
            self.capture_thread = threading.Thread(
                target=self._capture_loop_rpicam,
                daemon=True
            )
            self.capture_thread.start()
            
            logger.info("Camera capture started (rpicam-vid)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start rpicam-vid: {e}")
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
            
            if self.camera_type == 'picamera2' and self.camera:
                self.camera.stop()
            
            logger.info("Camera capture stopped")
            
        except Exception as e:
            logger.error(f"Error stopping camera: {e}")
    
    def cleanup(self):
        """Cleanup camera resources."""
        self.stop()
        
        try:
            if self.camera_type == 'picamera2' and self.camera:
                self.camera.close()
                self.camera = None
            logger.info("Camera resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up camera: {e}")
    
    def _capture_loop_picamera2(self):
        """Main capture loop for picamera2 - runs in separate thread."""
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
                logger.error(f"Error in picamera2 capture loop: {e}")
                self.error_count += 1
                self.last_error = str(e)
                
                retry_count += 1
                if retry_count > max_retries:
                    logger.error("Max retries exceeded, stopping capture")
                    self.is_running = False
                    break
                
                logger.info(f"Retrying capture in {retry_delay}s (attempt {retry_count}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10)
    
    def _capture_loop_rpicam(self):
        """Main capture loop for rpicam-vid - runs in separate thread."""
        retry_count = 0
        max_retries = 5
        retry_delay = 1
        
        while self.is_running:
            try:
                # Build rpicam-vid command
                cmd = [
                    'rpicam-vid',
                    '-t', '0',           # Run forever
                    '--inline',          # Output to stdout
                    '--width', str(self.width),
                    '--height', str(self.height),
                    '--framerate', str(self.fps),
                    '-o', '-'            # Output to stdout
                ]
                
                logger.info(f"Starting rpicam-vid: {' '.join(cmd)}")
                
                # Start process
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0
                )
                
                # Read stream
                while self.is_running and process.poll() is None:
                    timestamp = time.time()
                    
                    # Read frame data (H.264)
                    # rpicam-vid outputs H.264 encoded frames
                    # Each frame starts with specific markers (NALU start codes)
                    frame_data = b''
                    try:
                        # Use select to avoid blocking
                        ready = select.select([process.stdout], [], [], 0.1)
                        if ready[0]:
                            # Read some data
                            chunk = process.stdout.read(65536)  # 64KB chunks
                            if not chunk:
                                break
                            frame_data += chunk
                            
                            # Add to buffer if we have data
                            if frame_data:
                                self.buffer.put(frame_data, timestamp)
                                self.frame_count += 1
                                
                                # Call callback if set
                                if self.on_frame_callback:
                                    try:
                                        self.on_frame_callback(frame_data, timestamp)
                                    except Exception as e:
                                        logger.error(f"Error in frame callback: {e}")
                    except Exception as e:
                        logger.error(f"Error reading from rpicam-vid: {e}")
                        break
                
                # Clean up
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                
                # Reset retry count on success
                retry_count = 0
                
            except Exception as e:
                logger.error(f"Error in rpicam-vid capture loop: {e}")
                self.error_count += 1
                self.last_error = str(e)
                
                retry_count += 1
                if retry_count > max_retries:
                    logger.error("Max retries exceeded, stopping capture")
                    self.is_running = False
                    break
                
                logger.info(f"Retrying capture in {retry_delay}s (attempt {retry_count}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10)
    
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
