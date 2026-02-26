# Dockerfile for Pathway Smart Parking System
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies (with retries for network resilience)
RUN pip install --no-cache-dir --retries 3 --timeout 120 -r requirements.txt && \
    pip install --no-cache-dir --retries 3 --timeout 120 pathway

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
