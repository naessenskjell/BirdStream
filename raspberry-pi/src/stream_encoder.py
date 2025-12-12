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
        self.buffer_size = self.encoder_config.get('buffer_size', 4194304)  # 4MB default
        self.rbuffer_size = self.encoder_config.get('rbuffer_size', 52428800)  # 50MB receive buffer
        self.sbuffer_size = self.encoder_config.get('sbuffer_size', 52428800)  # 50MB send buffer
        self.max_packet_size = self.encoder_config.get('max_packet_size', 1316)
        
        self.video_capture = video_capture
        self.audio_capture = audio_capture
        
        self.process = None
        self.is_running = False
        self.encode_thread = None
        
        self.frame_count = 0
        self.error_count = 0
        self.last_error = None
        
        logger.info(f"Stream Encoder initialized: {self.encoder_type}")
        logger.info(f"Buffers: main={self.buffer_size//1024//1024}MB, rbuf={self.rbuffer_size//1024//1024}MB, sbuf={self.sbuffer_size//1024//1024}MB")
    
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
            
            # Build FFmpeg command with WiFi-friendly buffer settings
            # Larger buffers for WiFi outage tolerance
            cmd = [
                'ffmpeg',
                # Verbose logging to help diagnose RTMP I/O errors
                '-loglevel', 'debug',
                # Global options for reliability
                '-rtbufsize', str(self.rbuffer_size),  # 50MB receive buffer
                # NOTE: '-bufsize' is an encoding/output option — placed later before the output
            ]

            # Input video (from camera capture) - we send JPEG frames to stdin
            cmd += [
                '-f', 'mjpeg',  # Motion JPEG format
                '-i', 'pipe:0',  # Read from stdin
            ]

            # Optionally include audio input only if audio is enabled
            # Audio piping to a separate fd (pipe:3) is not implemented in this encoder
            # Disable passing a separate audio input to FFmpeg for now to avoid it waiting on a missing pipe.
            include_audio = False
            if self.audio_config.get('enabled', True) and getattr(self.audio_capture, 'enabled', True):
                logger.info("Audio capture enabled in config, but audio piping to ffmpeg is not implemented — starting without audio input")

            # Video encoding
            cmd += [
                '-vcodec', 'libx264',
                '-preset', self.preset,
                '-b:v', f"{self.video_config.get('bitrate', 4000)}k",
                '-pix_fmt', 'yuv420p',
                '-r', str(self.video_config.get('fps', 30)),
                '-maxrate', f"{int(self.video_config.get('bitrate', 4000) * 1.5)}k",  # Allow burst
            ]

            # Audio encoding (only if included)
            if include_audio:
                cmd += [
                    '-acodec', 'aac',
                    '-b:a', f"{self.audio_config.get('bitrate', 128)}k",
                    '-ar', str(self.audio_config.get('sample_rate', 48000)),
                ]

            # Sync settings
            cmd += [
                '-async', '1',  # Audio sync
                '-vsync', '1',  # Video sync
            ]

            # Additional reliability settings
            cmd += [
                '-fflags', 'nobuffer',  # Reduce latency
                '-flags', 'low_delay',  # Low delay mode
                '-max_delay', '500000',  # 500ms max delay
                '-probesize', '32',
                '-analyzeduration', '0',
            ]

            # RTMP/output settings with MTU-friendly packet size
            # Place encoding/output-specific options before the output URL to avoid "not a decoding option" warnings
            cmd += [
                '-bufsize', str(self.sbuffer_size),    # 50MB send buffer (output)
                '-flvflags', 'no_duration_filesize',
                '-packet_size', str(self.max_packet_size),
            ]

            # Output
            cmd += ['-f', 'flv', output_url]
            
            logger.info(f"FFmpeg command: {' '.join(cmd)}")
            
            # Start FFmpeg process with large buffers
            # Note: we only provide stdin for video; audio piping is not implemented yet.
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=self.buffer_size
            )

            # Start a thread to read FFmpeg stderr so we capture runtime errors
            def _stderr_reader(proc):
                try:
                    for line in iter(proc.stderr.readline, b''):
                        try:
                            text = line.decode(errors='replace').rstrip()
                            logger.info(f"ffmpeg: {text}")
                            try:
                                with open('/tmp/birdstream_ffmpeg.log', 'a', encoding='utf-8') as _f:
                                    _f.write(text + '\n')
                            except Exception:
                                pass
                        except Exception:
                            logger.info("ffmpeg: <non-decodable line>")
                except Exception as e:
                    logger.debug(f"FFmpeg stderr reader exited: {e}")

            threading.Thread(target=_stderr_reader, args=(self.process,), daemon=True).start()
            
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
