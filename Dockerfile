FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ffmpeg and rust (required for spotdl)
RUN apt-get update && \
    apt-get install -y ffmpeg curl build-essential && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Add cargo to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Create data directory for persistent files
RUN mkdir -p /app/data /app/downloads

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Move users.json to data directory if it exists, or create default
RUN if [ -f users.json ]; then \
        mv users.json /app/data/; \
    else \
        echo '{"users":[{"username":"admin","password_hash":"$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY.5AV2yAkHm1ha"}]}' > /app/data/users.json; \
    fi

# Expose port
EXPOSE 5000

# Run the application with increased timeout
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "--workers", "2", "app:app"] 