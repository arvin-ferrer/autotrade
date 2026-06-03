# Cryptocurrency Algorithmic Backtester & Live Bot

A high-performance, fully automated cryptocurrency quantitative trading architecture.

It seamlessly transitions from deep historical backtesting to 24/7 Live Paper Trading. Features an aggressively optimized **V2 Adaptive High-Beta Breakout Strategy**, dynamic Inverse-ATR position sizing, tick-by-tick ATR trailing stop ratcheting, Binance WebSocket integration, and a glassmorphic web dashboard for real-time portfolio monitoring.

---

## Core Features

- **V2 Breakout Engine:** A mathematically verified, bidirectional (Long/Short) strategy designed for the 4-hour timeframe. It uses Donchian Channels and ATR-based volatility filters to capture massive crypto breakouts.
- **Tick-by-Tick Risk Management:** Unlike traditional bots that wait for a candle to close, this bot evaluates ATR-based trailing stops and take-profits on every single Binance WebSocket tick, ratcheting up protection dynamically.
- **Inverse-ATR Risk Parity:** Automatically sizes positions based on current market volatility so you always risk exactly a fixed percentage (e.g., 1%) of your portfolio per trade, explicitly capped by a maximum leverage.
- **Perpetual Futures Simulation:** Accurately models real-world friction by applying simulated 0.05% taker fees, slippage, and 0.01% 8-hour funding rates for Long/Short positions.
- **Discord Integration:** Real-time push notifications to your phone for all executed entries, trailing stop triggers, and system shutdowns.
- **Glassmorphic Web Dashboard:** A stunning, fully-responsive dark-mode UI built with FastAPI that live-streams your portfolio balance and active positions.
- **Cloud Native:** Packaged with `docker-compose` for instant 24/7 deployment to any cloud provider.

---

## Quick Start (Local Paper Trading)

For full cloud deployment instructions, please read the [DEPLOY.md](DEPLOY.md) guide.

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
  --symbol "SOL/USDT,DOGE/USDT,ADA/USDT,LINK/USDT,DOT/USDT" \
  --timeframe 4h \
  --strategy breakout \
  --stop-mult 2.0 \
  --tp-mult 10.0 \
  --risk-pct 0.01
```

4. **Launch the Dashboard (In a separate terminal):**

```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000` to watch your portfolio!

---

## Backtesting Engine

Before risking capital, simulate years of historical data to prove the strategy works across different market regimes.

```bash
python scripts/breakout_v2_backtest.py
```
The backtester generates institutional metrics (Sharpe Ratio, Max Drawdown, CAGR) compared against a Buy & Hold benchmark.

---

## Project Architecture

```text
autotrade/
├── data/          # CCXT Historical Data Loaders & Caching
├── engine/        # The Quantitative Backtester & Simulator
├── strategies/    # Mathematical logic (Breakout, VolumeRSI)
├── live/          # The Live WebSocket Runner & Risk Executor
├── web/           # FastAPI Glassmorphic Dashboard
├── scripts/       # DB Management & Backtest Optimization Scripts
├── tests/         # Unit Tests & Verification Suites
├── docs/          # Research, System Blueprints, & Agent Plans
├── docker-compose.yml 
├── DEPLOY.md      
└── README.md      
```
