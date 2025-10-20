# Raspberry Pi Dockerfile
# Build container for streaming camera and audio to server
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for picamera2, pyaudio, and ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libjpeg-dev \
    libssl-dev \
    libffi-dev \
    libopenjp2-7 \
    libtiff6 \
    libwebp6 \
    libopenexr23 \
    libharfbuzz0b \
    libwebpmux3 \
    libopenjp2-tools \
    portaudio19-dev \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ .

# Create config directory
RUN mkdir -p /config

# Run the main application
CMD ["python", "main.py"]
