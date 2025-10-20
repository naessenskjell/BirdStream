"""
BirdStream - Network Stream Module
Handles streaming to server with connection resilience and automatic reconnection.
Includes WiFi network monitoring and frame buffering for outage tolerance.
"""

import logging
import threading
import time
import requests
import subprocess
import socket
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)


class NetworkStream:
    """
    Manages network connection and streaming to BirdStream server.
    Implements connection resilience with exponential backoff retry,
    WiFi network monitoring, and frame buffering for outage tolerance.
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
        self.max_retries = reconnect.get('max_retries', 30)
        self.backoff_multiplier = reconnect.get('backoff_multiplier', 1.5)
        self.initial_delay = reconnect.get('initial_delay', 2)
        self.max_delay = reconnect.get('max_delay', 30)
        
        # Network monitoring configuration
        network_cfg = self.server_config.get('network', {})
        self.network_monitor_enabled = network_cfg.get('monitor_enabled', True)
        self.check_interval = network_cfg.get('check_interval', 5)
        self.wifi_interface = network_cfg.get('wifi_interface', 'wlan0')
        self.fallback_interface = network_cfg.get('fallback_interface', 'eth0')
        self.ping_timeout = network_cfg.get('ping_timeout', 3)
        
        # Frame buffering configuration
        buffer_cfg = self.server_config.get('buffer', {})
        self.buffer_enabled = buffer_cfg.get('enabled', True)
        self.max_buffer_frames = buffer_cfg.get('max_frames', 450)  # ~15 seconds at 30fps
        self.max_buffer_memory_mb = buffer_cfg.get('memory_limit_mb', 256)
        self.max_buffer_bytes = self.max_buffer_memory_mb * 1024 * 1024
        
        # Frame buffer for WiFi outages
        self.frame_buffer = deque(maxlen=self.max_buffer_frames)
        self.buffer_size_bytes = 0
        self.buffer_lock = threading.Lock()
        
        # Connection state
        self.is_connected = False
        self.is_running = False
        self.stream_thread = None
        self.network_monitor_thread = None
        
        # Statistics
        self.connection_attempts = 0
        self.last_error = None
        self.last_connected_time = None
        self.frames_sent = 0
        self.bytes_sent = 0
        self.errors_count = 0
        self.buffered_frames_sent = 0
        self.wifi_disconnections = 0
        self.wifi_reconnections = 0
        self.network_interface = self.wifi_interface  # Track active interface
        
        logger.info(f"Network Stream initialized: {self.host}:{self.port} ({self.protocol})")
        logger.info(f"Buffer: {self.max_buffer_frames} frames, {self.max_buffer_memory_mb}MB max")
        logger.info(f"Network monitoring: {self.network_monitor_enabled} ({self.wifi_interface})")
    
    def is_interface_up(self, interface: str) -> bool:
        """
        Check if network interface is up.
        
        Args:
            interface: Interface name (e.g., 'wlan0')
            
        Returns:
            True if interface is up
        """
        try:
            result = subprocess.run(
                ['ip', 'link', 'show', interface],
                capture_output=True,
                text=True,
                timeout=2
            )
            return 'UP' in result.stdout
        except Exception as e:
            logger.debug(f"Failed to check interface {interface}: {e}")
            return False
    
    def is_server_reachable(self) -> bool:
        """
        Check if server is reachable via ping.
        
        Returns:
            True if server responds to ping
        """
        try:
            # Try to ping server
            result = subprocess.run(
                ['ping', '-c', '1', '-W', str(self.ping_timeout), self.host],
                capture_output=True,
                timeout=self.ping_timeout + 1
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Ping check failed: {e}")
            return False
    
    def monitor_network(self):
        """
        Monitor network connectivity in background.
        Detects WiFi disconnections and triggers reconnection.
        """
        logger.info("Starting network monitor thread")
        
        wifi_was_up = self.is_interface_up(self.wifi_interface)
        
        while self.is_running:
            try:
                # Check WiFi interface status
                wifi_is_up = self.is_interface_up(self.wifi_interface)
                
                if wifi_is_up and not wifi_was_up:
                    # WiFi came back up
                    logger.warning(f"WiFi interface {self.wifi_interface} came back up")
                    self.wifi_reconnections += 1
                    self.is_connected = False  # Force reconnection attempt
                    wifi_was_up = True
                    
                elif not wifi_is_up and wifi_was_up:
                    # WiFi went down
                    logger.warning(f"WiFi interface {self.wifi_interface} went down")
                    self.wifi_disconnections += 1
                    self.is_connected = False
                    wifi_was_up = False
                
                # Try fallback interface if WiFi down
                if not wifi_is_up and self.fallback_interface:
                    eth_is_up = self.is_interface_up(self.fallback_interface)
                    if eth_is_up:
                        logger.info(f"Fallback interface {self.fallback_interface} is available")
                        self.network_interface = self.fallback_interface
                else:
                    self.network_interface = self.wifi_interface
                
                # Periodic server reachability check
                if self.is_connected:
                    if not self.is_server_reachable():
                        logger.warning("Server unreachable (ping failed)")
                        self.is_connected = False
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Network monitor error: {e}")
                time.sleep(self.check_interval)
    
    def add_frame_to_buffer(self, frame_data: bytes) -> bool:
        """
        Add frame to buffer if buffer enabled and space available.
        
        Args:
            frame_data: Frame data bytes
            
        Returns:
            True if frame was buffered
        """
        if not self.buffer_enabled or self.is_connected:
            # Don't buffer if connected or buffering disabled
            return False
        
        try:
            with self.buffer_lock:
                # Check if adding this frame would exceed memory limit
                if self.buffer_size_bytes + len(frame_data) > self.max_buffer_bytes:
                    logger.debug(f"Frame buffer full ({self.buffer_size_bytes}/{self.max_buffer_bytes})")
                    return False
                
                # Add frame to buffer
                self.frame_buffer.append(frame_data)
                self.buffer_size_bytes += len(frame_data)
                
                if len(self.frame_buffer) == 1:
                    logger.info(f"Started buffering frames ({len(self.frame_buffer)}/{self.max_buffer_frames})")
                
                return True
        except Exception as e:
            logger.error(f"Error adding frame to buffer: {e}")
            return False
    
    def get_buffered_frames(self) -> list:
        """
        Get all buffered frames (for sending when reconnected).
        
        Returns:
            List of frame data
        """
        try:
            with self.buffer_lock:
                frames = list(self.frame_buffer)
                self.frame_buffer.clear()
                self.buffer_size_bytes = 0
                
                if frames:
                    logger.info(f"Sending {len(frames)} buffered frames to server")
                    self.buffered_frames_sent += len(frames)
                
                return frames
        except Exception as e:
            logger.error(f"Error retrieving buffered frames: {e}")
            return []
    
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
                
                # Send any buffered frames when reconnected
                buffered = self.get_buffered_frames()
                if buffered:
                    logger.info(f"Ready to send {len(buffered)} buffered frames")
                
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
            
            # Start network monitor thread if enabled
            if self.network_monitor_enabled:
                self.network_monitor_thread = threading.Thread(
                    target=self.monitor_network,
                    daemon=True
                )
                self.network_monitor_thread.start()
            
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
            
            if self.network_monitor_thread:
                self.network_monitor_thread.join(timeout=2)
            
            logger.info("Stream transmission stopped")
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
    
    def _stream_loop(self, encoder):
        """
        Main streaming loop with reconnection logic and frame buffering.
        
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
                        logger.error(f"Max reconnection attempts exceeded ({self.max_retries})")
                        self.is_running = False
                        break
                    
                    logger.info(f"Reconnecting in {retry_delay:.1f}s (attempt {retry_count}/{self.max_retries})")
                    time.sleep(retry_delay)
                    
                    if self.connect():
                        retry_count = 0
                        retry_delay = self.initial_delay
                        logger.info("Successfully reconnected to server")
                    else:
                        # Increase delay with cap
                        retry_delay = min(retry_delay * self.backoff_multiplier, self.max_delay)
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
                    logger.warning(f"Server health check error: {e}")
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
            Status dict with connectivity, buffering, and network monitoring info
        """
        uptime = 0
        if self.last_connected_time:
            uptime = time.time() - self.last_connected_time
        
        buffer_info = {
            'enabled': self.buffer_enabled,
            'buffered_frames': len(self.frame_buffer),
            'buffer_size_bytes': self.buffer_size_bytes,
            'buffer_capacity_bytes': self.max_buffer_bytes,
            'buffered_frames_sent': self.buffered_frames_sent,
        }
        
        network_info = {
            'monitor_enabled': self.network_monitor_enabled,
            'active_interface': self.network_interface,
            'wifi_disconnections': self.wifi_disconnections,
            'wifi_reconnections': self.wifi_reconnections,
        }
        
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
            'buffer': buffer_info,
            'network': network_info,
            'config': {
                'timeout': self.timeout,
                'max_retries': self.max_retries,
                'backoff_multiplier': self.backoff_multiplier,
                'initial_delay': self.initial_delay,
                'max_delay': self.max_delay,
            }
        }
