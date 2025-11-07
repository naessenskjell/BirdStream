Native deployment guide for Raspberry Pi (no Docker)

This document explains how to run the camera side of BirdStream natively on a Raspberry Pi. It assumes you have the repository cloned on the Pi under /home/pi/Documents/GitHub/BirdStream/raspberry-pi.

Prerequisites
- Raspberry Pi OS (Bullseye or later recommended)
- Python 3.11 or Python 3.9+ with virtualenv support
- libcamera and rpicam-apps installed on the host for rpicam-vid fallback (recommended)
- FFmpeg installed
- Camera enabled in raspi-config (if using picamera2/libcamera)

Quick steps
1. SSH into the Pi or open a terminal on the device.
2. Run the setup script (may prompt for sudo):
   sudo bash setup_pi.sh

3. Test rpicam-vid (optional, verifies system camera stack):
   rpicam-vid --width 640 --height 480 --output - | ffplay -

4. Run BirdStream manually (for debugging):
   bash run_birdstream.sh

5. Install systemd service (optional, to run on boot):
   sudo cp deploy/birdstream.service /etc/systemd/system/birdstream.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now birdstream.service

Notes and troubleshooting
- If you installed the repository in a different path, update the paths in deploy/birdstream.service accordingly.
- If rpicam-vid is not installed, camera_capture.py will attempt to use picamera2 if available. If both are missing, the script will fail.
- For device access, ensure user (pi) has permissions for /dev/video0 and audio devices. You can add user to groups: sudo usermod -a -G video,audio pi
- If you see camera errors, run raspi-config -> Interface Options -> Camera and enable the camera, then reboot.

Advanced: running under a dedicated user and virtualenv
- Create a system user if desired, change the User= in the service file, and ensure the WorkingDirectory and ExecStart point at the venv and main.py for that user.
