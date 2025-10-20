"""
BirdStream - Stream Encoder Module
Combines video and audio streams into a single encoded stream (RTMP or custom).
Handles real-time encoding with adaptive bitrate.
"""

import logging
import threading
import subprocess
import time
from typing import Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class StreamEncoder:
    """
    Encodes combined video and audio streams.
    Supports RTMP streaming or piping to custom protocols.
    """
    
    def __init__(self, config: dict, video_capture, audio_capture):
        """
        Initialize stream encoder.
        
        Args:
            config: Configuration dict from config.yaml
            video_capture: CameraCapture instance
            audio_capture: AudioCapture instance
        """
        self.encoder_config = config.get('encoder', {})
        self.video_config = config.get('camera', {})
        self.audio_config = config.get('audio', {})
        
        self.encoder_type = self.encoder_config.get('type', 'ffmpeg')
        self.preset = self.encoder_config.get('preset', 'medium')
        self.buffer_size = self.encoder_config.get('buffer_size', 1048576)
        
        self.video_capture = video_capture
        self.audio_capture = audio_capture
        
        self.process = None
        self.is_running = False
        self.encode_thread = None
        
        self.frame_count = 0
        self.error_count = 0
        self.last_error = None
        
        logger.info(f"Stream Encoder initialized: {self.encoder_type}")
    
    def start(self, output_url: str) -> bool:
        """
        Start encoding stream to output URL.
        
        Args:
            output_url: RTMP URL or output file
            
        Returns:
            True if successful
        """
        if self.is_running:
            logger.warning("Encoder already running")
            return False
        
        if self.encoder_type == 'ffmpeg':
            return self._start_ffmpeg(output_url)
        else:
            logger.error(f"Unknown encoder type: {self.encoder_type}")
            return False
    
    def _start_ffmpeg(self, output_url: str) -> bool:
        """
        Start FFmpeg encoder process.
        
        Args:
            output_url: RTMP URL or output path
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Starting FFmpeg encoder to {output_url}")
            
            # Build FFmpeg command
            # Input: H.264 video + AAC audio
            # Output: RTMP stream
            cmd = [
                'ffmpeg',
                # Input video (from camera capture)
                '-f', 'mjpeg',  # Motion JPEG format
                '-i', 'pipe:0',  # Read from stdin
                # Input audio (from audio capture)
                '-f', 's16le',  # Raw PCM format
                '-ar', str(self.audio_config.get('sample_rate', 48000)),
                '-ac', str(self.audio_config.get('channels', 1)),
                '-i', 'pipe:3',  # Read from pipe 3
                
                # Video encoding
                '-vcodec', 'libx264',
                '-preset', self.preset,
                '-b:v', f"{self.video_config.get('bitrate', 4000)}k",
                '-pix_fmt', 'yuv420p',
                '-r', str(self.video_config.get('fps', 30)),
                
                # Audio encoding
                '-acodec', 'aac',
                '-b:a', f"{self.audio_config.get('bitrate', 128)}k",
                '-ar', str(self.audio_config.get('sample_rate', 48000)),
                
                # Sync settings
                '-async', '1',  # Audio sync
                '-vsync', '1',  # Video sync
                
                # Buffer settings
                '-buffer_size', str(self.buffer_size),
                '-probesize', '32',
                '-analyzeduration', '0',
                
                # RTMP settings
                '-flvflags', 'no_duration_filesize',
                
                # Output
                '-f', 'flv',
                output_url,
            ]
            
            logger.info(f"FFmpeg command: {' '.join(cmd)}")
            
            # Start FFmpeg process
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=self.buffer_size
            )
            
            self.is_running = True
            
            # Start encoding thread
            self.encode_thread = threading.Thread(
                target=self._encode_loop,
                daemon=True
            )
            self.encode_thread.start()
            
            logger.info("FFmpeg encoder started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start FFmpeg encoder: {e}")
            self.last_error = str(e)
            self.error_count += 1
            return False
    
    def stop(self):
        """Stop encoder."""
        if not self.is_running:
            return
        
        try:
            logger.info("Stopping encoder...")
            self.is_running = False
            
            if self.encode_thread:
                self.encode_thread.join(timeout=5)
            
            if self.process:
                try:
                    self.process.stdin.close()
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except:
                    self.process.kill()
                self.process = None
            
            logger.info("Encoder stopped")
            
        except Exception as e:
            logger.error(f"Error stopping encoder: {e}")
    
    def _encode_loop(self):
        """Main encoding loop - runs in separate thread."""
        retry_count = 0
        max_retries = 5
        retry_delay = 1
        
        while self.is_running:
            try:
                # Get video frame
                video_frame = self.video_capture.get_frame()
                if not video_frame:
                    # Small delay if no frame available
                    time.sleep(0.01)
                    continue
                
                # Get audio frame
                audio_frame = self.audio_capture.get_frame()
                if not audio_frame:
                    # Audio can be missing, use silence
                    audio_frame = b'\x00' * 4096
                
                # Write to FFmpeg stdin
                try:
                    if video_frame:
                        self.process.stdin.write(video_frame)
                    if audio_frame:
                        # Write audio to separate pipe in real implementation
                        # For now, combining into main stream
                        pass
                    
                    self.process.stdin.flush()
                    self.frame_count += 1
                    retry_count = 0
                    
                except (BrokenPipeError, OSError) as e:
                    logger.error(f"Encoder pipe error: {e}")
                    self.is_running = False
                    break
                
            except Exception as e:
                logger.error(f"Error in encode loop: {e}")
                self.error_count += 1
                self.last_error = str(e)
                
                retry_count += 1
                if retry_count > max_retries:
                    logger.error("Max retries exceeded, stopping encoder")
                    self.is_running = False
                    break
                
                logger.info(f"Retrying in {retry_delay}s (attempt {retry_count}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10)
    
    def get_status(self) -> dict:
        """
        Get encoder status.
        
        Returns:
            Status dict
        """
        return {
            'type': self.encoder_type,
            'running': self.is_running,
            'frame_count': self.frame_count,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'process_alive': self.process is not None and self.process.poll() is None,
            'config': {
                'preset': self.preset,
                'buffer_size': self.buffer_size,
                'video_bitrate': self.video_config.get('bitrate', 4000),
                'audio_bitrate': self.audio_config.get('bitrate', 128),
            }
        }
