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

# Default: run the live trading bot
# Override via docker-compose command or docker run args
CMD ["python", "main_live.py", \
     "--strategy", "rsi", \
     "--rsi-window", "14", \
     "--rsi-oversold", "30", \
     "--rsi-overbought", "75", \
     "--stop-loss", "0.03", \
     "--take-profit", "0.10", \
     "--timeframe", "1h"]
