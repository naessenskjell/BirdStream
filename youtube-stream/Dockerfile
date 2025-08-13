# Use Ubuntu as base for FFmpeg support
FROM ubuntu:22.04

# Install system dependencies: Python, FFmpeg, and OpenCV deps
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python script and images
COPY stream_processor.py .
COPY overlays /app/overlays

# Expose the Flask port
EXPOSE 3000

# Set entrypoint to run the script
CMD ["python3", "stream_processor.py"]