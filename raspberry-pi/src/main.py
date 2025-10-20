#!/usr/bin/env python3
"""
BirdStream - Raspberry Pi Capture and Streaming Module
Main entry point for camera and audio capture and streaming to server.
"""

import logging
import sys
import time
import signal
import yaml
from pathlib import Path

# Import capture modules
from camera_capture import CameraCapture
from audio_capture import AudioCapture
from stream_encoder import StreamEncoder
from network_stream import NetworkStream

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BirdStreamApp:
    """Main BirdStream application."""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize BirdStream application.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = self.load_config(config_path)
        
        # Initialize components
        self.camera = CameraCapture(self.config)
        self.audio = AudioCapture(self.config)
        self.encoder = StreamEncoder(self.config, self.camera, self.audio)
        self.network = NetworkStream(self.config)
        
        self.is_running = False
        
        logger.info("BirdStream application initialized")
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration: {e}")
            sys.exit(1)
    
    def start(self) -> bool:
        """
        Start all components.
        
        Returns:
            True if all components started successfully
        """
        logger.info("Starting BirdStream components...")
        
        try:
            # Initialize hardware
            if not self.camera.initialize():
                logger.error("Failed to initialize camera")
                return False
            
            if not self.audio.initialize():
                logger.error("Failed to initialize audio")
                return False
            
            # Start capture
            if not self.camera.start():
                logger.error("Failed to start camera capture")
                return False
            
            if not self.audio.start():
                logger.error("Failed to start audio capture")
                return False
            
            # Connect to server
            if not self.network.connect():
                logger.error("Failed to connect to server")
                self.stop()
                return False
            
            # Start streaming
            server_url = f"rtmp://{self.config['server']['host']}:{self.config['server']['port']}/live"
            if not self.encoder.start(server_url):
                logger.error("Failed to start encoder")
                self.stop()
                return False
            
            if not self.network.start_streaming(self.encoder):
                logger.error("Failed to start network streaming")
                self.stop()
                return False
            
            self.is_running = True
            logger.info("BirdStream started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting BirdStream: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stop all components."""
        logger.info("Stopping BirdStream...")
        
        self.is_running = False
        
        try:
            self.network.stop_streaming()
            self.encoder.stop()
            self.audio.stop()
            self.camera.stop()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        try:
            self.audio.cleanup()
            self.camera.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        logger.info("BirdStream stopped")
    
    def get_status(self) -> dict:
        """Get status of all components."""
        return {
            'timestamp': time.time(),
            'running': self.is_running,
            'camera': self.camera.get_status(),
            'audio': self.audio.get_status(),
            'encoder': self.encoder.get_status(),
            'network': self.network.get_status(),
        }
    
    def run(self):
        """Run the application."""
        if not self.start():
            logger.error("Failed to start BirdStream")
            sys.exit(1)
        
        logger.info("BirdStream running. Press Ctrl+C to stop.")
        
        # Status reporting thread
        def status_reporter():
            while self.is_running:
                time.sleep(30)  # Report every 30 seconds
                if self.is_running:
                    status = self.get_status()
                    logger.info(f"Status: Camera={status['camera']['frame_count']} "
                              f"Audio={status['audio']['frame_count']} "
                              f"Network={status['network']['frames_sent']}")
        
        import threading
        reporter = threading.Thread(target=status_reporter, daemon=True)
        reporter.start()
        
        try:
            # Keep application running
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    sys.exit(0)


def main():
    """Main entry point."""
    logger.info("BirdStream - Raspberry Pi Camera & Audio Streamer")
    logger.info("=" * 50)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run application
    app = BirdStreamApp('config.yaml')
    app.run()


if __name__ == '__main__':
    main()
