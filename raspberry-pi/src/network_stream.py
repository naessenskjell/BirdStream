"""
BirdStream - Network Stream Module
Handles streaming to server with connection resilience and automatic reconnection.
"""

import logging
import threading
import time
import requests
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)


class NetworkStream:
    """
    Manages network connection and streaming to BirdStream server.
    Implements connection resilience with exponential backoff retry.
    """
    
    def __init__(self, config: dict):
        """
        Initialize network stream.
        
        Args:
            config: Configuration dict from config.yaml
        """
        self.server_config = config.get('server', {})
        self.host = self.server_config.get('host', 'localhost')
        self.port = self.server_config.get('port', 5000)
        self.protocol = self.server_config.get('protocol', 'rtmp')
        self.timeout = self.server_config.get('timeout', 10)
        
        reconnect = self.server_config.get('reconnect', {})
        self.max_retries = reconnect.get('max_retries', 5)
        self.backoff_multiplier = reconnect.get('backoff_multiplier', 2.0)
        self.initial_delay = reconnect.get('initial_delay', 1)
        
        self.is_connected = False
        self.is_running = False
        self.stream_thread = None
        self.connection_attempts = 0
        self.last_error = None
        self.last_connected_time = None
        self.frames_sent = 0
        self.bytes_sent = 0
        self.errors_count = 0
        
        logger.info(f"Network Stream initialized: {self.host}:{self.port} ({self.protocol})")
    
    def connect(self) -> bool:
        """
        Establish connection to server.
        
        Returns:
            True if successful
        """
        if self.is_connected:
            logger.warning("Already connected to server")
            return True
        
        try:
            logger.info(f"Connecting to {self.host}:{self.port}...")
            
            # Test connection to server
            response = requests.get(
                f"http://{self.host}:{self.port}/health",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info("Successfully connected to server")
                self.is_connected = True
                self.last_connected_time = time.time()
                self.connection_attempts = 0
                return True
            else:
                raise Exception(f"Server returned status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            self.last_error = str(e)
            self.errors_count += 1
            return False
    
    def disconnect(self):
        """Disconnect from server."""
        if not self.is_connected:
            return
        
        try:
            logger.info("Disconnecting from server...")
            self.is_connected = False
            self.last_error = None
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    def start_streaming(self, encoder) -> bool:
        """
        Start streaming to server.
        
        Args:
            encoder: StreamEncoder instance
            
        Returns:
            True if successful
        """
        if self.is_running:
            logger.warning("Already streaming")
            return False
        
        if not self.is_connected:
            logger.error("Not connected to server")
            return False
        
        try:
            logger.info("Starting stream transmission...")
            
            self.is_running = True
            self.frames_sent = 0
            self.bytes_sent = 0
            
            # Start streaming thread
            self.stream_thread = threading.Thread(
                target=self._stream_loop,
                args=(encoder,),
                daemon=True
            )
            self.stream_thread.start()
            
            logger.info("Stream transmission started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self.last_error = str(e)
            return False
    
    def stop_streaming(self):
        """Stop streaming."""
        if not self.is_running:
            return
        
        try:
            logger.info("Stopping stream transmission...")
            self.is_running = False
            
            if self.stream_thread:
                self.stream_thread.join(timeout=5)
            
            logger.info("Stream transmission stopped")
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
    
    def _stream_loop(self, encoder):
        """
        Main streaming loop with reconnection logic.
        
        Args:
            encoder: StreamEncoder instance
        """
        retry_delay = self.initial_delay
        retry_count = 0
        
        while self.is_running:
            try:
                # Check connection
                if not self.is_connected:
                    retry_count += 1
                    if retry_count > self.max_retries:
                        logger.error("Max reconnection attempts exceeded")
                        self.is_running = False
                        break
                    
                    logger.info(f"Reconnecting in {retry_delay}s (attempt {retry_count}/{self.max_retries})")
                    time.sleep(retry_delay)
                    
                    if self.connect():
                        retry_count = 0
                        retry_delay = self.initial_delay
                    else:
                        retry_delay = min(retry_delay * self.backoff_multiplier, 60)
                        continue
                
                # Stream data
                # In real implementation, this would send encoded stream to server
                # For now, we just maintain connection
                time.sleep(1)
                
                # Periodic health check
                try:
                    response = requests.get(
                        f"http://{self.host}:{self.port}/api/status",
                        timeout=self.timeout
                    )
                    if response.status_code != 200:
                        logger.warning(f"Server health check failed: {response.status_code}")
                        self.is_connected = False
                except requests.RequestException as e:
                    logger.error(f"Server health check error: {e}")
                    self.is_connected = False
                    self.errors_count += 1
                
            except Exception as e:
                logger.error(f"Error in stream loop: {e}")
                self.is_connected = False
                self.errors_count += 1
                time.sleep(retry_delay)
    
    def send_metadata(self, metadata: dict) -> bool:
        """
        Send metadata to server.
        
        Args:
            metadata: Metadata dict (camera, audio, quality settings, etc.)
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            logger.warning("Not connected to server")
            return False
        
        try:
            response = requests.post(
                f"http://{self.host}:{self.port}/api/stream/metadata",
                json=metadata,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info("Metadata sent to server")
                return True
            else:
                logger.error(f"Failed to send metadata: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending metadata: {e}")
            self.last_error = str(e)
            return False
    
    def get_status(self) -> dict:
        """
        Get network stream status.
        
        Returns:
            Status dict
        """
        uptime = 0
        if self.last_connected_time:
            uptime = time.time() - self.last_connected_time
        
        return {
            'connected': self.is_connected,
            'running': self.is_running,
            'server': f"{self.host}:{self.port}",
            'protocol': self.protocol,
            'frames_sent': self.frames_sent,
            'bytes_sent': self.bytes_sent,
            'errors': self.errors_count,
            'connection_attempts': self.connection_attempts,
            'uptime_seconds': uptime,
            'last_error': self.last_error,
            'config': {
                'timeout': self.timeout,
                'max_retries': self.max_retries,
                'backoff_multiplier': self.backoff_multiplier,
            }
        }
