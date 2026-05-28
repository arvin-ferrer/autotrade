#!/bin/bash
# ============================================================
#  BTC Algo Trader — Local Deployment Setup Script
#  Sets up systemd services for the trading bot and dashboard
#  so they run 24/7 in the background and auto-start on boot.
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python3"
VENV_UVICORN="${PROJECT_DIR}/venv/bin/uvicorn"
USER="$(whoami)"

echo "=============================================="
echo "  BTC Algo Trader — Local Service Installer"
echo "=============================================="
echo "Project:  ${PROJECT_DIR}"
echo "Python:   ${VENV_PYTHON}"
echo "User:     ${USER}"
echo ""

# Verify venv exists
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "ERROR: Virtual environment not found at ${VENV_PYTHON}"
    echo "Run: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

# ---- Service 1: Trading Bot ----
echo "[1/4] Creating trading bot service..."
sudo tee /etc/systemd/system/btc-trader.service > /dev/null << EOF
[Unit]
Description=BTC Algo Trading Bot (RSI 1h Strategy)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} main_live.py \\
    --strategy rsi \\
    --rsi-window 14 \\
    --rsi-oversold 30 \\
    --rsi-overbought 75 \\
    --stop-loss 0.03 \\
    --take-profit 0.10 \\
    --timeframe 1h
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ---- Service 2: Web Dashboard ----
echo "[2/4] Creating web dashboard service..."
sudo tee /etc/systemd/system/btc-dashboard.service > /dev/null << EOF
[Unit]
Description=BTC Algo Trader Web Dashboard (FastAPI)
After=network-online.target btc-trader.service
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_UVICORN} web.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ---- Enable & Start ----
echo "[3/4] Enabling services to start on boot..."
sudo systemctl daemon-reload
sudo systemctl enable btc-trader.service
sudo systemctl enable btc-dashboard.service

echo "[4/4] Starting services now..."
sudo systemctl start btc-trader.service
sudo systemctl start btc-dashboard.service

echo ""
echo "=============================================="
echo "  ✅ DEPLOYMENT COMPLETE!"
echo "=============================================="
echo ""
echo "Both services are running and will auto-start on reboot."
echo ""
echo "Useful commands:"
echo "  View bot logs:        journalctl -u btc-trader -f"
echo "  View dashboard logs:  journalctl -u btc-dashboard -f"
echo "  Stop bot:             sudo systemctl stop btc-trader"
echo "  Stop dashboard:       sudo systemctl stop btc-dashboard"
echo "  Restart bot:          sudo systemctl restart btc-trader"
echo "  Check status:         sudo systemctl status btc-trader btc-dashboard"
echo ""
echo "Dashboard:  http://localhost:8000"
echo ""
