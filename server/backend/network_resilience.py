"""
BirdStream - Network Resilience Module
Handles reconnection state management and automatic recovery.
"""

import logging
import threading
import time
from typing import Callable, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class StreamState(Enum):
    """Stream state enumeration."""
    OFF = "off"
    LIVE = "live"
    RECONNECTING = "reconnecting"
    STATIC = "static"
    ERROR = "error"


class NetworkResilience:
    """
    Manages stream resilience with automatic reconnection and fallback.
    Handles transitions between LIVE, RECONNECTING, STATIC, and ERROR states.
    """
    
    def __init__(self, stream_handler, youtube_rtmp, static_images):
        """
        Initialize network resilience manager.
        
        Args:
            stream_handler: StreamHandler instance
            youtube_rtmp: YouTubeRTMP instance
            static_images: StaticImageHandler instance
        """
        self.stream_handler = stream_handler
        self.youtube_rtmp = youtube_rtmp
        self.static_images = static_images
        
        self.current_state = StreamState.OFF
        self.previous_state = None
        self.state_changed_at = datetime.now()
        
        self.is_monitoring = False
        self.monitor_thread = None
        
        self.reconnect_attempts = 0
        self.reconnect_max_attempts = 10
        self.reconnect_delay = 2  # seconds
        
        self.last_error = None
        self.error_count = 0
        self.recovery_count = 0
        
        # Callbacks
        self.on_state_change: Optional[Callable] = None
        
        logger.info("Network Resilience manager initialized")
    
    def set_state(self, new_state: StreamState, reason: str = ""):
        """
        Set stream state with transition logic.
        
        Args:
            new_state: New StreamState
            reason: Reason for state change
        """
        if new_state == self.current_state:
            return
        
        old_state = self.current_state
        self.previous_state = old_state
        self.current_state = new_state
        self.state_changed_at = datetime.now()
        
        state_transition = f"{old_state.value} -> {new_state.value}"
        message = f"State transition: {state_transition}"
        if reason:
            message += f" ({reason})"
        
        logger.info(message)
        
        # Call callback
        if self.on_state_change:
            try:
                self.on_state_change(old_state, new_state, reason)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
    
    def check_stream_health(self) -> tuple:
        """
        Check health of current stream.
        
        Returns:
            Tuple (video_ok, audio_ok)
        """
        conn = self.stream_handler.get_active_connection()
        if not conn:
            return False, False
        
        return conn.video_ok, conn.audio_ok
    
    def handle_video_loss(self):
        """Handle loss of video stream."""
        logger.warning("Video stream lost")
        
        if self.current_state == StreamState.LIVE:
            self.set_state(StreamState.RECONNECTING, "Video lost")
            self.start_recovery()
    
    def handle_audio_loss(self):
        """Handle loss of audio stream."""
        logger.warning("Audio stream lost")
        
        if self.current_state == StreamState.LIVE:
            # Audio loss is not critical, we can continue
            logger.info("Continuing stream despite audio loss")
    
    def handle_full_stream_loss(self):
        """Handle loss of entire stream (video + audio)."""
        logger.error("Complete stream loss")
        
        if self.current_state == StreamState.LIVE:
            self.set_state(StreamState.RECONNECTING, "Stream lost")
            self.start_recovery()
        elif self.current_state == StreamState.STATIC:
            self.set_state(StreamState.RECONNECTING, "Fallback stream lost")
            self.start_recovery()
    
    def start_recovery(self) -> bool:
        """
        Start automatic recovery process.
        
        Returns:
            True if recovery initiated
        """
        if self.current_state == StreamState.RECONNECTING:
            logger.info("Recovery already in progress")
            return False
        
        logger.info("Starting stream recovery process")
        self.set_state(StreamState.RECONNECTING, "Recovery initiated")
        self.reconnect_attempts = 0
        self.recovery_count += 1
        
        # Start recovery monitoring
        if not self.is_monitoring:
            self.start_monitoring()
        
        return True
    
    def attempt_recovery(self) -> bool:
        """
        Attempt to recover stream.
        
        Returns:
            True if recovery successful
        """
        self.reconnect_attempts += 1
        
        logger.info(f"Recovery attempt {self.reconnect_attempts}/{self.reconnect_max_attempts}")
        
        # Check if original stream has recovered
        video_ok, audio_ok = self.check_stream_health()
        
        if video_ok:
            logger.info("Stream recovered!")
            self.set_state(StreamState.LIVE, "Stream recovered")
            self.reconnect_attempts = 0
            return True
        
        # If max attempts reached, fallback to static image
        if self.reconnect_attempts >= self.reconnect_max_attempts:
            logger.warning("Max recovery attempts reached, falling back to static image")
            self.set_state(StreamState.STATIC, "Recovery failed, using static image")
            self.start_static_fallback()
            return False
        
        # Try again after delay
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 60)
        logger.info(f"Next recovery attempt in {delay}s")
        
        return False
    
    def start_static_fallback(self) -> bool:
        """
        Start fallback to static image.
        
        Returns:
            True if successful
        """
        try:
            logger.info("Starting static image fallback")
            
            if not self.static_images.get_current_image_path():
                if not self.static_images.get_images():
                    logger.error("No images available for fallback")
                    self.set_state(StreamState.ERROR, "No fallback images")
                    return False
                
                # Select first available image
                self.static_images.select_image(self.static_images.get_images()[0])
            
            # Start static image stream
            # Note: In real implementation, would stream to YouTube
            if self.static_images.start_streaming("rtmps://fallback"):
                logger.info("Static image fallback started")
                return True
            
            logger.error("Failed to start static image fallback")
            self.set_state(StreamState.ERROR, "Fallback startup failed")
            return False

    def handle_stream_recovery(self) -> bool:
        """
        Trigger recovery action for a live stream: if an active ingest exists and
        a YouTube stream key is configured, start publishing the ingest to YouTube.
        Returns True if a publish was started or recovery initiated.
        """
        try:
            conn = self.stream_handler.get_active_connection()
            if not conn:
                logger.warning("No active connection to recover/publish")
                return False

            # If YouTube is configured, attempt to publish
            if self.youtube_rtmp and self.youtube_rtmp.get_stream_key():
                # Common local RTMP source from nginx
                source = 'rtmp://localhost:1935/live/live0'
                success = self.youtube_rtmp.start_from_rtmp(source)
                if success:
                    self.set_state(StreamState.LIVE, 'Publishing to YouTube')
                    logger.info('Publishing ingest to YouTube started')
                    return True
                else:
                    logger.error('Failed to start YouTube publishing')
                    return False

            # Nothing to do; fall back to starting recovery monitor
            self.start_recovery()
            return True

        except Exception as e:
            logger.error(f"Error handling stream recovery: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Error starting fallback: {e}")
            self.last_error = str(e)
            self.error_count += 1
            self.set_state(StreamState.ERROR, str(e))
            return False
    
    def stop_fallback(self):
        """Stop static image fallback."""
        try:
            self.static_images.stop_streaming()
        except Exception as e:
            logger.error(f"Error stopping fallback: {e}")
    
    def start_monitoring(self):
        """Start resilience monitoring."""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Resilience monitoring started")
    
    def stop_monitoring(self):
        """Stop resilience monitoring."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("Resilience monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                video_ok, audio_ok = self.check_stream_health()
                
                if self.current_state == StreamState.LIVE:
                    # Check for stream loss
                    if not video_ok or not audio_ok:
                        if not video_ok and not audio_ok:
                            self.handle_full_stream_loss()
                        elif not video_ok:
                            self.handle_video_loss()
                        else:
                            self.handle_audio_loss()
                
                elif self.current_state == StreamState.RECONNECTING:
                    # Attempt recovery
                    self.attempt_recovery()
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(1)
    
    def get_status(self) -> dict:
        """Get resilience status."""
        video_ok, audio_ok = self.check_stream_health()
        uptime = (datetime.now() - self.state_changed_at).total_seconds()
        
        return {
            'current_state': self.current_state.value,
            'previous_state': self.previous_state.value if self.previous_state else None,
            'state_uptime_seconds': uptime,
            'video_ok': video_ok,
            'audio_ok': audio_ok,
            'reconnect_attempts': self.reconnect_attempts,
            'reconnect_max_attempts': self.reconnect_max_attempts,
            'recovery_count': self.recovery_count,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'monitoring': self.is_monitoring,
        }
