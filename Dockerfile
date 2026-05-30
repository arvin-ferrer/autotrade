FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for some pip packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Create data cache directory
RUN mkdir -p data/.cache

# Expose the dashboard port
EXPOSE 8000

# Default: run both the live trading bot and the web dashboard
CMD ["bash", "start.sh"]
