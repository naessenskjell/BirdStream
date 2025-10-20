"""
BirdStream - Static Image Handler Module
Serves static images when stream is unavailable or in fallback mode.
"""

import logging
import os
import threading
import subprocess
from typing import Optional, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class StaticImageHandler:
    """
    Manages static image serving and fallback streaming.
    Handles image upload, rotation, and conversion to video stream.
    """
    
    def __init__(self, image_directory: str = 'images'):
        """
        Initialize static image handler.
        
        Args:
            image_directory: Directory to store uploaded images
        """
        self.image_dir = Path(image_directory)
        self.image_dir.mkdir(exist_ok=True)
        
        self.current_image = None
        self.available_images: List[str] = []
        self.is_streaming = False
        self.process = None
        self.stream_thread = None
        
        self.frames_sent = 0
        self.errors = 0
        self.last_error = None
        
        # Scan for existing images
        self._scan_images()
        
        logger.info(f"Static Image Handler initialized with directory: {image_directory}")
    
    def _scan_images(self):
        """Scan directory for available images."""
        try:
            supported = {'.jpg', '.jpeg', '.png', '.bmp'}
            images = [
                f.name for f in self.image_dir.iterdir()
                if f.suffix.lower() in supported
            ]
            self.available_images = sorted(images)
            logger.info(f"Found {len(self.available_images)} images")
        except Exception as e:
            logger.error(f"Error scanning images: {e}")
    
    def upload_image(self, filename: str, file_content: bytes) -> bool:
        """
        Upload and store an image.
        
        Args:
            filename: Original filename
            file_content: Image file bytes
            
        Returns:
            True if successful
        """
        try:
            # Validate filename
            name = Path(filename).name
            if not name:
                raise ValueError("Invalid filename")
            
            # Validate file size (max 10MB)
            if len(file_content) > 10 * 1024 * 1024:
                raise ValueError("File too large (max 10MB)")
            
            # Save file
            file_path = self.image_dir / name
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            logger.info(f"Image uploaded: {name} ({len(file_content)} bytes)")
            self._scan_images()
            
            # Auto-select first image
            if not self.current_image and self.available_images:
                self.current_image = self.available_images[0]
                logger.info(f"Auto-selected image: {self.current_image}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error uploading image: {e}")
            self.last_error = str(e)
            self.errors += 1
            return False
    
    def delete_image(self, filename: str) -> bool:
        """
        Delete an image.
        
        Args:
            filename: Image filename
            
        Returns:
            True if deleted
        """
        try:
            file_path = self.image_dir / filename
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Image deleted: {filename}")
                
                # If deleted image was selected, pick another
                if self.current_image == filename:
                    self._scan_images()
                    self.current_image = self.available_images[0] if self.available_images else None
                    logger.info(f"Selected new image: {self.current_image}")
                else:
                    self._scan_images()
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting image: {e}")
            self.last_error = str(e)
            return False
    
    def select_image(self, filename: str) -> bool:
        """
        Select which image to serve.
        
        Args:
            filename: Image filename
            
        Returns:
            True if selected
        """
        if filename not in self.available_images:
            logger.error(f"Image not found: {filename}")
            return False
        
        self.current_image = filename
        logger.info(f"Selected image: {filename}")
        return True
    
    def get_images(self) -> list:
        """Get list of available images."""
        return self.available_images
    
    def get_current_image_path(self) -> Optional[str]:
        """Get full path to current image."""
        if not self.current_image:
            return None
        
        path = self.image_dir / self.current_image
        if path.exists():
            return str(path)
        
        return None
    
    def start_streaming(self, output_url: str) -> bool:
        """
        Start streaming static image as video (for YouTube fallback).
        Creates a video stream from the selected image.
        
        Args:
            output_url: RTMP output URL
            
        Returns:
            True if successful
        """
        if not self.current_image:
            logger.error("No image selected")
            return False
        
        if self.is_streaming:
            logger.warning("Already streaming")
            return True
        
        image_path = self.get_current_image_path()
        if not image_path:
            logger.error("Image file not found")
            return False
        
        try:
            logger.info(f"Starting static image stream: {self.current_image}")
            
            # Create video from static image
            # Loop image at 1fps with silent audio
            cmd = [
                'ffmpeg',
                '-loop', '1',
                '-i', image_path,
                '-f', 'lavfi',
                '-i', 'anullsrc=r=48000:cl=mono',
                
                # Video encoding
                '-vcodec', 'libx264',
                '-preset', 'medium',
                '-b:v', '4000k',
                '-r', '30',
                '-pix_fmt', 'yuv420p',
                
                # Audio (silent)
                '-acodec', 'aac',
                '-b:a', '0',  # No audio
                
                # Sync
                '-shortest',
                '-async', '1',
                '-vsync', '1',
                
                # RTMP
                '-flvflags', 'no_duration_filesize',
                
                # Output
                '-f', 'flv',
                output_url,
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            
            self.is_streaming = True
            self.frames_sent = 0
            
            # Start monitoring thread
            self.stream_thread = threading.Thread(
                target=self._monitor_stream,
                daemon=True
            )
            self.stream_thread.start()
            
            logger.info("Static image stream started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start image stream: {e}")
            self.last_error = str(e)
            self.errors += 1
            return False
    
    def stop_streaming(self):
        """Stop streaming static image."""
        if not self.is_streaming:
            return
        
        try:
            logger.info("Stopping static image stream...")
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
            
            logger.info("Static image stream stopped")
            
        except Exception as e:
            logger.error(f"Error stopping image stream: {e}")
    
    def _monitor_stream(self):
        """Monitor image stream process."""
        while self.is_streaming:
            try:
                if self.process and self.process.poll() is not None:
                    logger.error(f"Image stream process exited with code {self.process.returncode}")
                    self.is_streaming = False
                    self.errors += 1
                    break
                
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error monitoring image stream: {e}")
                break
    
    def is_alive(self) -> bool:
        """Check if stream is alive."""
        if not self.is_streaming or not self.process:
            return False
        
        return self.process.poll() is None
    
    def get_status(self) -> dict:
        """Get static image handler status."""
        return {
            'streaming': self.is_streaming,
            'alive': self.is_alive(),
            'current_image': self.current_image,
            'available_images': self.available_images,
            'frames_sent': self.frames_sent,
            'errors': self.errors,
            'last_error': self.last_error,
            'image_directory': str(self.image_dir),
        }
