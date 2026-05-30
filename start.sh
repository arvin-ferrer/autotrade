#!/bin/bash

# Start the KAMA Trading Engine in the background
echo "Starting KAMA Trading Engine..."
python main_csm.py &
BOT_PID=$!

# Start the FastAPI Web Dashboard in the foreground
echo "Starting Web Dashboard..."
export PORT=${PORT:-8000}
python web/app.py

# If the web server crashes or stops, also kill the background bot
kill $BOT_PID
