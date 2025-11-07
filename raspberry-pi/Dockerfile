# Raspberry Pi Dockerfile
# Build container for streaming camera and audio to server
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for picamera2, pyaudio, and ffmpeg
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    build-essential \
    ffmpeg \
    libjpeg-dev \
    libssl-dev \
    libffi-dev \
    libopenjp2-7 \
    libtiff6 \
    libwebp7 \
    libopenexr-3-1-30 \
    libharfbuzz0b \
    libwebpmux3 \
    libopenjp2-tools \
    libcap-dev \
    portaudio19-dev \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# Install libcamera and rpicam runtime dependencies
# Since rpicam-apps is not in Debian repos, we'll use the Python fallback approach
# The camera_capture.py will automatically fall back to rpicam-vid if available
# For now, we focus on getting the basic libraries that rpicam-vid needs
RUN apt-get update && apt-get install -y \
    libcamera0 \
    libcamera-tools \
    liblz4-1 \
    libdrm2 \
    libyaml-0.2 \
    || true && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ .

# Create config directory
RUN mkdir -p /config

# Run the main application
CMD ["python", "main.py"]
