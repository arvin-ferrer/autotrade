# Institutional-Grade Crypto Algorithmic Trader (Live Ready)

A high-performance, fully automated cryptocurrency quantitative trading architecture. 

It seamlessly transitions from deep historical backtesting to 24/7 Live Paper Trading. Features an aggressively optimized Multi-Asset VolumeRSI Breakout Strategy, sub-second tick-by-tick risk management (Stop-Loss/Take-Profit), Binance WebSocket integration, and a beautiful glassmorphic web dashboard for real-time portfolio monitoring.

---

##  Core Features

- **The VolumeRSI Breakout Engine:** A mathematically verified momentum strategy that dynamically scales RSI using Volume Moving Averages to catch massive crypto breakouts while filtering out low-volume chop.
- **Tick-by-Tick Risk Management:** Unlike traditional bots that wait for a candle to close, this bot analyzes sub-second Binance WebSocket ticks to execute 1% emergency stop-losses in real-time, preventing flash-crash liquidations.
- **Multi-Coin Streaming:** Concurrently tracks and trades an entire basket of assets (`BTC/USDT`, `ETH/USDT`, `SOL/USDT`) simultaneously on a single lightweight process.
- **Discord Integration:** Real-time push notifications to your phone for all executed BUY/SELL orders, Stop-Loss triggers, and system shutdowns.
- **Glassmorphic Web Dashboard:** A stunning, fully-responsive dark-mode UI built with FastAPI that live-streams your portfolio balance, active positions, and fiat currency conversions (e.g. PHP/USD).
- **Cloud Native:** Packaged with `docker-compose` for instant deployment to Google Cloud, Oracle Cloud, or AWS.

---

##  Live Trading Deployment

For full cloud deployment instructions (including Google Cloud setup, fixing Docker SQLite bugs, and configuring `.env` keys), please read the [DEPLOY.md](DEPLOY.md) guide.

### Quick Start (Local Paper Trading)

1. **Clone and Install:**
```bash
git clone https://github.com/YOUR_USERNAME/autotrade.git
cd autotrade
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Configure Environment:**
```bash
cp .env.example .env
nano .env # Add your Discord Webhook URL here
```

3. **Start the Live Multi-Coin Bot:**
```bash
python main_live.py \
  --symbol "BTC/USDT,ETH/USDT,SOL/USDT" \
  --timeframe 1h \
  --strategy volumersi \
  --stop-loss 0.01 \
  --take-profit 0.10 \
  --rsi-oversold 35.0 \
  --vol-multiplier 2.0
```

4. **Launch the Dashboard (In a separate terminal):**
```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000` to watch your portfolio grow!

---

##  Backtesting Engine

Before risking capital, you can simulate years of historical data to prove the strategy works across different market regimes (Bull Markets, Bear Markets, Sideways Chop).

### Run a Robustness Sweep
```bash
python main.py \
  --strategy volumersi \
  --symbol BTC/USDT \
  --timeframe 1h \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --capital 500000.0 \
  --plot strategy_performance.png
```

The backtester models capital constraints, fractional shares, taker fee structures (e.g., 0.1%), and generates institutional metrics (Sharpe Ratio, Max Drawdown, Profit Factor) compared against Buy & Hold.

---

##  Project Architecture

```text
autotrade/
├── data/          # CCXT Historical Data Loaders & Caching
├── engine/        # The Quantitative Backtester & Simulator
├── strategies/    # Mathematical logic (VolumeRSI, MACD, EMA)
├── live/          # The Live WebSocket Runner & Risk Executor
├── web/           # FastAPI Glassmorphic Dashboard
├── scripts/       # DB Management & Hyperparameter Optimizers
├── tests/         # Unit Tests & Verification Suites
├── docs/          # Research, System Blueprints, & Agent Plans
├── docker-compose.yml 
├── DEPLOY.md      
└── README.md      
```
