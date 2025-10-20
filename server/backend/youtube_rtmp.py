"""
BirdStream - YouTube RTMP Module
Handles streaming to YouTube Live with key management and monitoring.
"""

import logging
import threading
import subprocess
import time
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class YouTubeRTMP:
    """
    Manages YouTube Live streaming via RTMP.
    Handles key validation, stream startup, and monitoring.
    """
    
    def __init__(self, settings_manager=None):
        """
        Initialize YouTube RTMP handler.
        
        Args:
            settings_manager: SettingsManager instance for storing keys
        """
        self.settings_manager = settings_manager
        self.stream_key = None
        self.youtube_url = "rtmps://a.rtmp.youtube.com/live2"
        
        self.process = None
        self.is_streaming = False
        self.stream_thread = None
        
        self.started_at = None
        self.frames_sent = 0
        self.bytes_sent = 0
        self.errors = 0
        self.last_error = None
        
        logger.info("YouTube RTMP handler initialized")
    
    def set_stream_key(self, key: str) -> bool:
        """
        Set YouTube stream key.
        
        Args:
            key: YouTube stream key
            
        Returns:
            True if valid
        """
        if not key or len(key) < 10:
            logger.error("Invalid YouTube stream key format")
            return False
        
        self.stream_key = key
        
        # Save to persistent storage if available
        if self.settings_manager:
            try:
                self.settings_manager.set('youtube_stream_key', key)
                logger.info("YouTube stream key saved")
            except Exception as e:
                logger.error(f"Failed to save stream key: {e}")
        
        return True
    
    def get_stream_key(self) -> Optional[str]:
        """Get current stream key."""
        return self.stream_key
    
    def load_stream_key(self) -> bool:
        """
        Load stream key from persistent storage.
        
        Returns:
            True if key was loaded
        """
        if not self.settings_manager:
            return False
        
        try:
            key = self.settings_manager.get('youtube_stream_key')
            if key:
                self.stream_key = key
                logger.info("YouTube stream key loaded from storage")
                return True
        except Exception as e:
            logger.error(f"Failed to load stream key: {e}")
        
        return False
    
    def start(self, video_source, audio_source) -> bool:
        """
        Start streaming to YouTube.
        
        Args:
            video_source: Video input (file/pipe)
            audio_source: Audio input (file/pipe)
            
        Returns:
            True if successful
        """
        if not self.stream_key:
            logger.error("YouTube stream key not set")
            return False
        
        if self.is_streaming:
            logger.warning("Already streaming to YouTube")
            return True
        
        try:
            logger.info("Starting YouTube stream...")
            
            # Build FFmpeg command
            cmd = [
                'ffmpeg',
                '-re',  # Read at native frame rate
                
                # Input video
                '-f', 'h264',
                '-i', video_source,
                
                # Input audio
                '-f', 'aac',
                '-i', audio_source,
                
                # Video encoding
                '-vcodec', 'copy',  # Don't re-encode
                '-acodec', 'aac',
                '-b:a', '128k',
                
                # Sync
                '-async', '1',
                '-vsync', '1',
                
                # RTMP specific
                '-flvflags', 'no_duration_filesize',
                
                # Output to YouTube
                '-f', 'flv',
                f'{self.youtube_url}/{self.stream_key}',
            ]
            
            logger.info("Starting FFmpeg for YouTube streaming")
            
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            
            self.is_streaming = True
            self.started_at = datetime.now()
            self.frames_sent = 0
            
            # Start monitoring thread
            self.stream_thread = threading.Thread(
                target=self._monitor_stream,
                daemon=True
            )
            self.stream_thread.start()
            
            logger.info("YouTube streaming started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start YouTube stream: {e}")
            self.last_error = str(e)
            self.errors += 1
            return False
    
    def stop(self):
        """Stop streaming to YouTube."""
        if not self.is_streaming:
            return
        
        try:
            logger.info("Stopping YouTube stream...")
            self.is_streaming = False
            
            if self.stream_thread:
                self.stream_thread.join(timeout=5)
            
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except:
                    self.process.kill()
                self.process = None
            
            logger.info("YouTube stream stopped")
            
        except Exception as e:
            logger.error(f"Error stopping YouTube stream: {e}")
    
    def _monitor_stream(self):
        """Monitor YouTube stream process."""
        while self.is_streaming:
            try:
                if self.process and self.process.poll() is not None:
                    # Process has ended
                    logger.error(f"YouTube stream process exited with code {self.process.returncode}")
                    stdout, stderr = self.process.communicate()
                    if stderr:
                        logger.error(f"FFmpeg stderr: {stderr.decode()[:500]}")
                    self.is_streaming = False
                    self.errors += 1
                    break
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error monitoring stream: {e}")
                break
    
    def is_alive(self) -> bool:
        """Check if stream is alive and running."""
        if not self.is_streaming or not self.process:
            return False
        
        return self.process.poll() is None
    
    def get_status(self) -> dict:
        """Get YouTube streaming status."""
        uptime = 0
        if self.started_at:
            uptime = (datetime.now() - self.started_at).total_seconds()
        
        return {
            'enabled': self.stream_key is not None,
            'streaming': self.is_streaming,
            'alive': self.is_alive(),
            'youtube_url': self.youtube_url,
            'frames_sent': self.frames_sent,
            'bytes_sent': self.bytes_sent,
            'errors': self.errors,
            'last_error': self.last_error,
            'uptime_seconds': uptime,
            'started_at': self.started_at.isoformat() if self.started_at else None,
        }
