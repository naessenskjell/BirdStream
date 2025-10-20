"""
BirdStream - Settings Manager Module
Manages persistent configuration and sensitive data storage.
"""

import logging
import json
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SettingsManager:
    """
    Manages application settings with persistent storage.
    Handles YouTube stream key and other configuration.
    """
    
    def __init__(self, config_file: str = 'settings.json'):
        """
        Initialize settings manager.
        
        Args:
            config_file: Path to settings JSON file
        """
        self.config_file = Path(config_file)
        self.settings = {}
        
        # Default settings
        self.defaults = {
            'youtube_stream_key': '',
            'youtube_enabled': False,
            'static_image_fallback': True,
            'auto_recover': True,
            'recovery_timeout': 30,
            'max_recovery_attempts': 10,
            'stream_bitrate': 4000,
            'stream_fps': 30,
            'image_upload_limit': 100,  # MB
        }
        
        # Initialize with defaults
        self.settings = self.defaults.copy()
        
        # Load from file
        self.load()
        
        logger.info(f"Settings Manager initialized with file: {config_file}")
    
    def load(self) -> bool:
        """
        Load settings from file.
        
        Returns:
            True if successful
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                
                # Merge with defaults (to handle new settings)
                self.settings = self.defaults.copy()
                self.settings.update(loaded)
                
                logger.info(f"Settings loaded from {self.config_file}")
                return True
            else:
                logger.info("Settings file not found, using defaults")
                self.settings = self.defaults.copy()
                return False
        
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.settings = self.defaults.copy()
            return False
    
    def save(self) -> bool:
        """
        Save settings to file.
        
        Returns:
            True if successful
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            
            logger.info(f"Settings saved to {self.config_file}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    def set(self, key: str, value: Any) -> bool:
        """
        Set a setting value.
        
        Args:
            key: Setting key
            value: New value
            
        Returns:
            True if successful
        """
        try:
            old_value = self.settings.get(key)
            self.settings[key] = value
            
            # Log sensitive changes (without values)
            if key == 'youtube_stream_key':
                logger.info(f"Setting updated: {key}")
            else:
                logger.info(f"Setting updated: {key} = {value}")
            
            # Auto-save
            self.save()
            return True
        
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        return self.settings.get(key, default)
    
    def get_all(self) -> dict:
        """
        Get all settings (non-sensitive).
        
        Returns:
            Settings dict (excludes sensitive keys)
        """
        # Filter out sensitive data
        sensitive_keys = {'youtube_stream_key'}
        return {
            k: v for k, v in self.settings.items()
            if k not in sensitive_keys
        }
    
    def delete(self, key: str) -> bool:
        """
        Delete a setting.
        
        Args:
            key: Setting key
            
        Returns:
            True if deleted
        """
        try:
            if key in self.settings:
                del self.settings[key]
                logger.info(f"Setting deleted: {key}")
                self.save()
                return True
            return False
        
        except Exception as e:
            logger.error(f"Error deleting setting: {e}")
            return False
    
    def reset(self) -> bool:
        """
        Reset all settings to defaults.
        
        Returns:
            True if successful
        """
        try:
            self.settings = self.defaults.copy()
            self.save()
            logger.info("Settings reset to defaults")
            return True
        
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            return False
    
    def validate_youtube_key(self, key: str) -> bool:
        """
        Validate YouTube stream key format.
        
        Args:
            key: Stream key to validate
            
        Returns:
            True if valid
        """
        # YouTube stream keys are typically 40+ characters
        # and contain alphanumeric characters
        if not key:
            return False
        
        if len(key) < 10:
            return False
        
        # Check for valid characters (alphanumeric + dashes)
        if not all(c.isalnum() or c == '-' for c in key):
            return False
        
        return True
    
    def get_status(self) -> dict:
        """Get settings manager status."""
        return {
            'config_file': str(self.config_file),
            'file_exists': self.config_file.exists(),
            'settings_count': len(self.settings),
            'has_youtube_key': bool(self.get('youtube_stream_key')),
            'youtube_enabled': self.get('youtube_enabled', False),
        }
