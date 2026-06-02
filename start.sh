#!/bin/bash

# Start the V2 Breakout Trading Engine in the background
echo "Starting V2 Breakout Trading Engine..."
python main_live.py &
BOT_PID=$!

# Start the FastAPI Web Dashboard in the foreground
echo "Starting Web Dashboard..."
export PORT=${PORT:-8000}
python web/app.py

# If the web server crashes or stops, also kill the background bot
kill $BOT_PID
