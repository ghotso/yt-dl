FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create downloads directory
RUN mkdir -p downloads

# Expose port
EXPOSE 5000

# Run the application with increased timeout
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "--workers", "2", "app:app"] 