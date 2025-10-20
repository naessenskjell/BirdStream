"""
BirdStream - Logger Module
Implements structured logging with metrics and connection statistics.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional, List
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


class StreamLogger:
    """
    Structured logger for stream events and metrics.
    """
    
    def __init__(self, log_dir: str = 'logs', max_entries: int = 1000):
        """
        Initialize stream logger.
        
        Args:
            log_dir: Directory for log files
            max_entries: Maximum log entries to keep in memory
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.max_entries = max_entries
        self.log_entries = deque(maxlen=max_entries)
        
        # Setup file logging
        self.log_file = self.log_dir / 'birdstream.log'
        self.setup_file_logging()
        
        logger.info(f"Stream Logger initialized, log file: {self.log_file}")
    
    def setup_file_logging(self):
        """Setup file-based logging with rotation."""
        try:
            # Create rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                str(self.log_file),
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            
            # Add to root logger
            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            
            logger.info("File logging configured")
        except Exception as e:
            logger.error(f"Error setting up file logging: {e}")
    
    def log_event(self, level: str, event_type: str, message: str, data: dict = None):
        """
        Log a structured event.
        
        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            event_type: Type of event (connection, stream, error, etc.)
            message: Log message
            data: Additional data dict
        """
        try:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'level': level,
                'type': event_type,
                'message': message,
                'data': data or {},
            }
            
            self.log_entries.append(entry)
            
            # Log via standard logger
            log_func = getattr(logging, level.lower())
            log_func(f"[{event_type}] {message}")
            
        except Exception as e:
            logger.error(f"Error logging event: {e}")
    
    def get_recent_logs(self, count: int = 50, event_type: Optional[str] = None) -> list:
        """
        Get recent log entries.
        
        Args:
            count: Number of entries to return
            event_type: Optional filter by event type
            
        Returns:
            List of log entries
        """
        entries = list(self.log_entries)
        
        if event_type:
            entries = [e for e in entries if e['type'] == event_type]
        
        # Return last 'count' entries
        return entries[-count:]
    
    def get_stats(self) -> dict:
        """Get logging statistics."""
        return {
            'total_entries': len(self.log_entries),
            'max_entries': self.max_entries,
            'log_file': str(self.log_file),
            'log_file_exists': self.log_file.exists(),
        }


class MetricsCollector:
    """
    Collects and aggregates performance metrics.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.metrics = {
            'video': {
                'frames': 0,
                'bytes': 0,
                'errors': 0,
                'last_frame_time': None,
            },
            'audio': {
                'frames': 0,
                'bytes': 0,
                'errors': 0,
                'last_frame_time': None,
            },
            'stream': {
                'total_uptime': 0,
                'reconnections': 0,
                'fallbacks': 0,
            },
        }
    
    def record_video_frame(self, bytes_size: int):
        """Record video frame."""
        self.metrics['video']['frames'] += 1
        self.metrics['video']['bytes'] += bytes_size
        self.metrics['video']['last_frame_time'] = datetime.now().isoformat()
    
    def record_audio_frame(self, bytes_size: int):
        """Record audio frame."""
        self.metrics['audio']['frames'] += 1
        self.metrics['audio']['bytes'] += bytes_size
        self.metrics['audio']['last_frame_time'] = datetime.now().isoformat()
    
    def record_video_error(self):
        """Record video error."""
        self.metrics['video']['errors'] += 1
    
    def record_audio_error(self):
        """Record audio error."""
        self.metrics['audio']['errors'] += 1
    
    def record_reconnection(self):
        """Record reconnection event."""
        self.metrics['stream']['reconnections'] += 1
    
    def record_fallback(self):
        """Record fallback to static image."""
        self.metrics['stream']['fallbacks'] += 1
    
    def get_metrics(self) -> dict:
        """Get collected metrics."""
        video_bitrate = 0
        audio_bitrate = 0
        
        if self.metrics['video']['frames'] > 0:
            # Estimate bitrate (bytes per frame * frames per second at 30fps)
            video_bitrate = (self.metrics['video']['bytes'] / self.metrics['video']['frames']) * 30 / 1000
        
        if self.metrics['audio']['frames'] > 0:
            audio_bitrate = (self.metrics['audio']['bytes'] / self.metrics['audio']['frames']) * 30 / 1000
        
        return {
            'video': {
                **self.metrics['video'],
                'estimated_bitrate_kbps': video_bitrate,
            },
            'audio': {
                **self.metrics['audio'],
                'estimated_bitrate_kbps': audio_bitrate,
            },
            'stream': self.metrics['stream'],
        }
    
    def reset(self):
        """Reset metrics."""
        self.__init__()


class ConnectionStatistics:
    """
    Tracks connection-related statistics.
    """
    
    def __init__(self):
        """Initialize connection statistics."""
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'total_uptime_hours': 0,
            'connection_drops': 0,
            'recovery_attempts': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'last_error': None,
            'last_error_time': None,
        }
    
    def record_new_connection(self):
        """Record new connection."""
        self.stats['total_connections'] += 1
        self.stats['active_connections'] += 1
    
    def record_disconnection(self):
        """Record disconnection."""
        if self.stats['active_connections'] > 0:
            self.stats['active_connections'] -= 1
        self.stats['connection_drops'] += 1
    
    def record_recovery_attempt(self):
        """Record recovery attempt."""
        self.stats['recovery_attempts'] += 1
    
    def record_successful_recovery(self):
        """Record successful recovery."""
        self.stats['successful_recoveries'] += 1
    
    def record_failed_recovery(self):
        """Record failed recovery."""
        self.stats['failed_recoveries'] += 1
    
    def record_error(self, error_message: str):
        """Record error."""
        self.stats['last_error'] = error_message
        self.stats['last_error_time'] = datetime.now().isoformat()
    
    def get_stats(self) -> dict:
        """Get statistics."""
        return self.stats.copy()
    
    def reset(self):
        """Reset statistics."""
        self.__init__()
