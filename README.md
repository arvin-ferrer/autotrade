# Cyptocurrency Algorithmic Backtester (AutoTrade)

A high-performance, modular, and extensible Python-based algorithmic trading backtester. It retrieves historical cryptocurrency data directly from exchanges (via CCXT), caches candles locally, runs technical trading strategies, simulates trades (accounting for transaction fees and slippage), and computes comprehensive portfolio performance metrics.

---

## Features

- **Robust Data Engine:** Direct exchange integration using CCXT with automatic local CSV caching and exponential backoff retry handling.
- **Quantitative Strategy Module:** Extendable strategy interface with out-of-the-box implementations for Moving Average Crossover (SMA/EMA) and Relative Strength Index (RSI) momentum.
- **Transaction Simulator:** Chronological simulation loop modeling capital, fractional asset shares, taker fee structures, and slippage.
- **Risk & Performance Analytics:** Computes key performance metrics (Sharpe ratio, Max Drawdown, Profit Factor, Win Rate, and Annualized Return/CAGR) comparing results to Buy & Hold.
- **Dual Visualizations:** Automatic rendering of terminal ASCII trendlines and saving high-quality dual-subplot PNG charts showing trade signals overlaying price alongside portfolio equity growth.

---

## Getting Started

### 1. Prerequisites

- Python 3.10+ (Fully compatible with Python 3.14+)

### 2. Setup Virtual Environment

Run the following commands to initialize the virtual environment and install the required dependencies:

```bash
# Create virtual environment
python3 -m venv venv

# Activate and install packages
./venv/bin/pip install -r requirements.txt
```

### 3. Run a Backtest

By default, executing the script runs a daily (1d) Moving Average Crossover backtest for BTC/USDT for the year 2025:

```bash
./venv/bin/python3 main.py
```

### 4. Customizing Parameters

You can customize the backtester via CLI arguments:

```bash
# Run the RSI strategy on 1-hour candles for a specific month
./venv/bin/python3 main.py \
  --strategy rsi \
  --timeframe 1h \
  --start 2025-05-01 \
  --end 2025-06-01 \
  --capital 5000.0 \
  --fee 0.00075 \
  --plot my_rsi_backtest.png

# Run EMA crossover strategy with custom MA windows
./venv/bin/python3 main.py \
  --strategy crossover \
  --ma-type ema \
  --fast-window 10 \
  --slow-window 30 \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --plot ema_crossover_run.png
```

---

## Project Architecture

```text
autotrade/
├── data/
│   ├── __init__.py
│   └── loader.py          # Fetches CCXT data and caches to CSV files
├── strategies/
│   ├── __init__.py
│   ├── base.py            # Base Strategy abstract class
│   └── simple.py          # SMA/EMA Crossover and RSI strategies
├── engine/
│   ├── __init__.py
│   ├── simulator.py       # Simulates entries, exits, position sizes, and fees
│   └── stats.py           # Computes CAGR, Sharpe, Drawdown, Profit Factor
├── utils/
│   ├── __init__.py
│   └── plots.py           # Generates ASCII trendlines and Matplotlib graphics
├── requirements.txt       # Essential packages (ccxt, pandas, matplotlib, tabulate)
├── main.py                # Main CLI dashboard entrypoint
└── README.md              # Project documentation
```

---

## CLI Options

| Argument | Type | Default | Description |
|---|---|---|---|
| `--symbol` | `str` | `'BTC/USDT'` | Ticker symbol to query |
| `--timeframe` | `str` | `'1d'` | Time period per candle (`1d`, `1h`, `15m`, etc.) |
| `--start` | `str` | `'2025-01-01'` | Start date in YYYY-MM-DD |
| `--end` | `str` | `'2025-12-31'` | End date in YYYY-MM-DD |
| `--strategy` | `str` | `'crossover'` | Active strategy (`crossover` or `rsi`) |
| `--capital` | `float` | `10000.0` | Initial capital to trade with (USDT) |
| `--fee` | `float` | `0.001` | Transaction fee rate (e.g. 0.001 = 0.1%) |
| `--slippage` | `float` | `0.0` | Slippage rate (e.g. 0.0005 = 0.05%) |
| `--fast-window` | `int` | `20` | Fast MA period (Moving Average strategy) |
| `--slow-window` | `int` | `50` | Slow MA period (Moving Average strategy) |
| `--ma-type` | `str` | `'sma'` | Moving average type: `sma` or `ema` |
| `--rsi-window` | `int` | `14` | RSI calculation window |
| `--rsi-overbought` | `float` | `70.0` | RSI overbought sell threshold |
| `--rsi-oversold` | `float` | `30.0` | RSI oversold buy threshold |
| `--plot` | `str` | `'equity_curve.png'` | Saved filename for the performance chart |
