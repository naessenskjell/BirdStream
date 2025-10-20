# Server Dockerfile
# Build container for receiving and routing video/audio streams
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for ffmpeg, nginx-compatible streaming
RUN apt-get update && apt-get install -y \
    ffmpeg \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY backend/ .

# Copy frontend static files
COPY frontend/ ./static/

# Create directories for persistent data
RUN mkdir -p /app/images /app/logs /app/uploads

# Expose web interface port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/status')" || exit 1

# Run the application
CMD ["python", "app.py"]
