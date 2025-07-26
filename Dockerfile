FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY duckstatsd/ ./duckstatsd/
COPY scripts/ ./scripts/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Create data directory for SQLite database
RUN mkdir -p /data

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose ports
EXPOSE 8125/udp 5000/tcp

# Set default environment variables
ENV DUCKSTATSD_HOST=0.0.0.0
ENV DUCKSTATSD_PORT=8125
ENV DUCKSTATSD_WEB_HOST=0.0.0.0
ENV DUCKSTATSD_WEB_PORT=5000
ENV DUCKSTATSD_DB_PATH=/data/metrics.db

# Use entrypoint script
ENTRYPOINT ["docker-entrypoint.sh"]