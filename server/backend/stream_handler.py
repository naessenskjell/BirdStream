"""
BirdStream - Stream Handler Module
Receives and manages incoming video and audio streams from Raspberry Pi.
"""

import logging
import threading
import time
from typing import Callable, Optional, Tuple
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


class StreamBuffer:
    """
    Thread-safe buffer for storing incoming stream chunks.
    Tracks video and audio streams separately for resilience.
    """
    
    def __init__(self, max_frames: int = 500):
        """
        Initialize stream buffer.
        
        Args:
            max_frames: Maximum frames to buffer
        """
        self.video_buffer = deque(maxlen=max_frames)
        self.audio_buffer = deque(maxlen=max_frames)
        self.lock = threading.Lock()
        
        self.video_frames = 0
        self.audio_frames = 0
        self.video_bytes = 0
        self.audio_bytes = 0
        self.last_video_time = None
        self.last_audio_time = None
    
    def put_video(self, data: bytes, timestamp: float) -> bool:
        """Add video frame to buffer."""
        with self.lock:
            try:
                self.video_buffer.append({
                    'data': data,
                    'timestamp': timestamp,
                    'size': len(data)
                })
                self.video_frames += 1
                self.video_bytes += len(data)
                self.last_video_time = time.time()
                return True
            except Exception as e:
                logger.error(f"Error adding video frame: {e}")
                return False
    
    def put_audio(self, data: bytes, timestamp: float) -> bool:
        """Add audio frame to buffer."""
        with self.lock:
            try:
                self.audio_buffer.append({
                    'data': data,
                    'timestamp': timestamp,
                    'size': len(data)
                })
                self.audio_frames += 1
                self.audio_bytes += len(data)
                self.last_audio_time = time.time()
                return True
            except Exception as e:
                logger.error(f"Error adding audio frame: {e}")
                return False
    
    def get_video(self) -> Optional[dict]:
        """Get next video frame (FIFO)."""
        with self.lock:
            if len(self.video_buffer) > 0:
                return self.video_buffer.popleft()
            return None
    
    def get_audio(self) -> Optional[dict]:
        """Get next audio frame (FIFO)."""
        with self.lock:
            if len(self.audio_buffer) > 0:
                return self.audio_buffer.popleft()
            return None
    
    def get_all_video(self) -> list:
        """Get all video frames and clear buffer."""
        with self.lock:
            frames = list(self.video_buffer)
            self.video_buffer.clear()
            return frames
    
    def get_all_audio(self) -> list:
        """Get all audio frames and clear buffer."""
        with self.lock:
            frames = list(self.audio_buffer)
            self.audio_buffer.clear()
            return frames
    
    def clear(self):
        """Clear all buffers."""
        with self.lock:
            self.video_buffer.clear()
            self.audio_buffer.clear()
    
    def get_stats(self) -> dict:
        """Get buffer statistics."""
        with self.lock:
            return {
                'video': {
                    'frames': len(self.video_buffer),
                    'total_frames': self.video_frames,
                    'total_bytes': self.video_bytes,
                    'last_frame': self.last_video_time,
                },
                'audio': {
                    'frames': len(self.audio_buffer),
                    'total_frames': self.audio_frames,
                    'total_bytes': self.audio_bytes,
                    'last_frame': self.last_audio_time,
                }
            }


class StreamConnection:
    """
    Represents a single stream connection from a Raspberry Pi.
    Tracks connection state, health, and statistics.
    """
    
    def __init__(self, connection_id: str):
        """
        Initialize stream connection.
        
        Args:
            connection_id: Unique identifier for this connection
        """
        self.id = connection_id
        self.buffer = StreamBuffer(max_frames=500)
        
        self.connected_at = datetime.now()
        self.last_activity = time.time()
        self.is_active = True
        
        self.video_ok = False
        self.audio_ok = False
        
        self.connection_drops = 0
        self.last_error = None
        
        logger.info(f"Stream connection created: {connection_id}")
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()
    
    def check_timeout(self, timeout_seconds: int = 30) -> bool:
        """
        Check if connection has timed out.
        
        Args:
            timeout_seconds: Timeout threshold
            
        Returns:
            True if timed out
        """
        elapsed = time.time() - self.last_activity
        if elapsed > timeout_seconds:
            logger.warning(f"Connection {self.id} timed out after {elapsed:.1f}s")
            return True
        return False
    
    def get_status(self) -> dict:
        """Get connection status."""
        uptime = (datetime.now() - self.connected_at).total_seconds()
        stats = self.buffer.get_stats()
        
        return {
            'id': self.id,
            'active': self.is_active,
            'uptime_seconds': uptime,
            'video_ok': self.video_ok,
            'audio_ok': self.audio_ok,
            'connection_drops': self.connection_drops,
            'last_error': self.last_error,
            'buffer': stats,
        }


class StreamHandler:
    """
    Main stream handler - receives and manages incoming streams.
    Implements reconnection logic and stream health monitoring.
    """
    
    def __init__(self):
        """Initialize stream handler."""
        self.connections: dict = {}  # id -> StreamConnection
        self.lock = threading.Lock()
        
        self.is_running = False
        self.monitor_thread = None
        self.total_connections = 0
        
        logger.info("Stream Handler initialized")
    
    def register_connection(self, connection_id: str) -> StreamConnection:
        """
        Register a new stream connection.
        
        Args:
            connection_id: Unique connection identifier
            
        Returns:
            StreamConnection object
        """
        with self.lock:
            if connection_id in self.connections:
                logger.warning(f"Connection {connection_id} already exists")
                return self.connections[connection_id]
            
            conn = StreamConnection(connection_id)
            self.connections[connection_id] = conn
            self.total_connections += 1
            
            logger.info(f"Registered connection: {connection_id} (total: {len(self.connections)})")
            return conn
    
    def get_connection(self, connection_id: str) -> Optional[StreamConnection]:
        """Get existing connection."""
        with self.lock:
            return self.connections.get(connection_id)
    
    def unregister_connection(self, connection_id: str) -> bool:
        """
        Unregister stream connection.
        
        Args:
            connection_id: Connection to remove
            
        Returns:
            True if removed
        """
        with self.lock:
            if connection_id in self.connections:
                conn = self.connections.pop(connection_id)
                logger.info(f"Unregistered connection: {connection_id}")
                return True
            return False
    
    def get_active_connection(self) -> Optional[StreamConnection]:
        """
        Get the currently active stream connection.
        
        Returns:
            Active StreamConnection or None
        """
        with self.lock:
            for conn in self.connections.values():
                if conn.is_active:
                    return conn
            return None
    
    def receive_video(self, connection_id: str, data: bytes, timestamp: float) -> bool:
        """
        Receive video frame from Raspberry Pi.
        
        Args:
            connection_id: Source connection
            data: Video frame data
            timestamp: Frame timestamp
            
        Returns:
            True if successful
        """
        conn = self.get_connection(connection_id)
        if not conn:
            logger.error(f"Connection {connection_id} not found")
            return False
        
        if conn.buffer.put_video(data, timestamp):
            conn.update_activity()
            conn.video_ok = True
            return True
        
        return False
    
    def receive_audio(self, connection_id: str, data: bytes, timestamp: float) -> bool:
        """
        Receive audio frame from Raspberry Pi.
        
        Args:
            connection_id: Source connection
            data: Audio frame data
            timestamp: Frame timestamp
            
        Returns:
            True if successful
        """
        conn = self.get_connection(connection_id)
        if not conn:
            logger.error(f"Connection {connection_id} not found")
            return False
        
        if conn.buffer.put_audio(data, timestamp):
            conn.update_activity()
            conn.audio_ok = True
            return True
        
        return False
    
    def start_monitoring(self, timeout_seconds: int = 30):
        """
        Start connection monitoring thread.
        
        Args:
            timeout_seconds: Timeout threshold for inactive connections
        """
        if self.is_running:
            logger.warning("Monitoring already running")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(timeout_seconds,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Stream monitoring started")
    
    def stop_monitoring(self):
        """Stop connection monitoring thread."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("Stream monitoring stopped")
    
    def _monitor_loop(self, timeout_seconds: int):
        """
        Monitor stream connections for timeouts and health.
        
        Args:
            timeout_seconds: Timeout threshold
        """
        while self.is_running:
            try:
                with self.lock:
                    # Check each connection
                    dead_connections = []
                    
                    for conn_id, conn in self.connections.items():
                        if conn.check_timeout(timeout_seconds):
                            logger.warning(f"Connection {conn_id} is stale")
                            dead_connections.append(conn_id)
                        
                        # Check stream health
                        stats = conn.buffer.get_stats()
                        
                        # If no video for 5 seconds, mark as disconnected
                        if conn.video_ok and conn.buffer.last_video_time:
                            video_age = time.time() - conn.buffer.last_video_time
                            if video_age > 5:
                                logger.warning(f"Connection {conn_id} video stale: {video_age:.1f}s")
                                conn.video_ok = False
                        
                        # If no audio for 5 seconds, mark as disconnected (but don't fail)
                        if conn.audio_ok and conn.buffer.last_audio_time:
                            audio_age = time.time() - conn.buffer.last_audio_time
                            if audio_age > 5:
                                logger.warning(f"Connection {conn_id} audio stale: {audio_age:.1f}s")
                                conn.audio_ok = False
                    
                    # Remove dead connections
                    for conn_id in dead_connections:
                        self.connections.pop(conn_id, None)
                        logger.info(f"Removed stale connection: {conn_id}")
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(1)
    
    def get_all_connections(self) -> list:
        """Get all connection statuses."""
        with self.lock:
            return [conn.get_status() for conn in self.connections.values()]
    
    def get_status(self) -> dict:
        """Get overall stream handler status."""
        with self.lock:
            connections = list(self.connections.values())
            active = sum(1 for c in connections if c.is_active)
            video_ok = sum(1 for c in connections if c.video_ok)
            audio_ok = sum(1 for c in connections if c.audio_ok)
            
            total_video_bytes = sum(c.buffer.video_bytes for c in connections)
            total_audio_bytes = sum(c.buffer.audio_bytes for c in connections)
            
            return {
                'total_connections': len(connections),
                'active_connections': active,
                'video_ok': video_ok,
                'audio_ok': audio_ok,
                'total_video_bytes': total_video_bytes,
                'total_audio_bytes': total_audio_bytes,
                'total_connections_ever': self.total_connections,
                'connections': [c.get_status() for c in connections],
            }
