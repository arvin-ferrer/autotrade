# Project Walkthrough: Modular Bitcoin Algorithmic Backtester

We have successfully completed all phases of the project, building a modular, high-performance Bitcoin backtester in `/home/arvin/Project/btc-algo-trader`. 

The project was implemented using a **Multi-Agent Team** structure consisting of two specialized subagents and ourselves coordinating as the Orchestrator.

---

## What We Accomplished

1. **Environment Initialization:** Initialized a virtual environment (`venv`) and resolved package compilation issues for Python 3.14.4 by using unpinned modern package versions.
2. **Data Module (`data_agent`):** Created a robust CCXT-powered exchange loader with automatic CSV caching to minimize API calls.
3. **Strategy Module (`strategy_agent`):** Built an indicator pipeline featuring SMA/EMA Moving Average Crossovers and Relative Strength Index (RSI) momentum signals.
4. **Backtesting Engine (`backtester_agent`):** Wrote an event-driven loop to simulate long-only entries/exits, transaction fees (0.1%), and slippage, returning complete history and trade logs.
5. **Analytics Engine (`backtester_agent`):** Computes Total Return, CAGR, Buy & Hold Return, Sharpe Ratio, Max Drawdown, Win Rate, and Profit Factor.
6. **CLI Runner & Visualizer (Orchestrator):** Created an interactive command-line interface with `tabulate` dashboard reports, terminal ASCII trendlines, and high-quality Matplotlib graphics (`equity_curve.png`).

---

## File Structure Created

All files are located in your repository directory [btc-algo-trader/](file:///home/arvin/Project/btc-algo-trader/):

```text
btc-algo-trader/
├── data/
│   ├── __init__.py        # Exposes public data loader
│   └── loader.py          # Downloads exchange prices via CCXT, caching to CSV
├── strategies/
│   ├── __init__.py        # Exposes strategy classes
│   ├── base.py            # Abstract BaseStrategy template
│   └── simple.py          # SMA/EMA Crossover and RSI strategy calculations
├── engine/
│   ├── __init__.py        # Exposes simulator and metrics calculator
│   ├── simulator.py       # Simulates entries, exits, fees, and daily equity tracking
│   └── stats.py           # Computes CAGR, Sharpe, max drawdown, profit factor
├── utils/
│   ├── __init__.py        # Exposes visual charting functions
│   └── plots.py           # Generates Matplotlib images and terminal ASCII charts
├── requirements.txt       # Dependencies (ccxt, pandas, matplotlib, tabulate, websockets)
├── main.py                # Main user CLI entrypoint script
└── README.md              # Documentation on options and configuration
```

---

## Live Validation Results

We ran the CLI script end-to-end for the year **2025** using a daily **SMA Crossover Strategy (20/50)** with **$10,000.00 USDT starting capital** and **0.1% transaction fees**:

```bash
./venv/bin/python3 main.py --start 2025-01-01 --end 2025-12-31 --capital 10000
```

### Trades Executed
During the year 2025, the strategy identified and completed **3 trades**:

| # | Entry Date | Exit Date | Entry Price | Exit Price | Size | Profit | Return % | Total Fee |
|---|------------|-----------|-------------|------------|------|--------|----------|-----------|
| 1 | 2025-04-24 | 2025-06-29 | $93,980.47 | $108,356.93 | 0.106299 BTC | +$1,506.69 | +15.07% | $21.51 |
| 2 | 2025-07-08 | 2025-08-25 | $108,922.98 | $110,111.98 | 0.105535 BTC | +$102.37 | +0.89% | $23.12 |
| 3 | 2025-09-27 | 2025-10-23 | $109,635.85 | $110,078.18 | 0.105782 BTC | +$23.55 | +0.20% | $23.24 |

### Performance Summary
The strategy successfully outperformed the asset's benchmark return:

* **Initial Capital:** $10,000.00 USDT
* **Final Portfolio Value:** $11,632.61 USDT
* **Total Return (%):** **+16.33%**
* **Buy & Hold Return (%):** **-7.34%** (Outperformed by 23.67%!)
* **Sharpe Ratio:** 0.8035
* **Maximum Drawdown (%):** 14.62%
* **Win Rate (%):** 100.00%
* **Profit Factor:** Infinity (no losing trades)

---

## Visualizing Performance
The runner automatically generates and saves a visual performance chart:
* **Default Output Path:** [equity_curve.png](file:///home/arvin/Project/btc-algo-trader/equity_curve.png)

This chart contains two panels:
1. **Upper Panel:** BTC/USDT price curve over time with green arrows for **Buy** entries and red arrows for **Sell** exits.
2. **Lower Panel:** Portfolio value curve comparing your algorithmic return (Blue) against the Buy & Hold benchmark (Orange).

---

## Phase 6: Live Paper Trading Framework (Transition to Real-World)

We added a parallel execution module in `live/` to run the strategy on real-time data using WebSockets, with transaction logs saved to a local SQLite database.

### ️ Localization & Regional Settings
* **Currency Support:** The paper portfolio uses **Philippine Peso (₱)**. A configurable exchange conversion rate (default 58.5) calculates balances, sizes, and fees in PHP, while pricing remains in the exchange standard USD.
* **Timezone Offset:** All timestamps logged to the console, database, and Discord alerts are formatted in **Philippine Time (PHT, UTC+8)**.

###  Alert System: Discord Webhook Integration
When a trade signal is executed, the executor builds and sends a rich embed payload to a Discord Webhook. It includes:
* Buy entries (Green embed) displaying size in BTC, entry price in USD/PHP, transaction fee, and current portfolio estimate.
* Sell exits (Green if profitable, Red if loss) showing size, sell price, net cash received in PHP, fee paid, and trade profit/loss with percentages.
* Connection warning alerts (Orange embed) if WebSockets disconnect.
* Startup/Manual shutdown notification cards (Blue / Red embeds).

---

## Running Live Paper Trading

### 1. Setup Environment
Create a `.env` file in the root directory using `.env.example` as a template:
```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_here
PHP_USD_RATE=58.5
```

### 2. Run the Live Bot
Execute the live runner:
```bash
./venv/bin/python3 main_live.py --timeframe 1m --initial-cash 500000
```

### 3. Verification Log Sample
```text
[DB] Initialized paper portfolio with ₱500,000.00 PHP at 2026-05-27 14:07:41 PHT
=======================================================
      LIVE CRYPTO PAPER TRADING CLIENT (PHP/PHT)
=======================================================
Start Time:      2026-05-27 14:07:41 PHT
Exchange:        Binance Spot (Real-time WebSockets)
Trading Symbol:  BTC/USDT
Timeframe:       1m
Strategy:        CROSSOVER
Exchange Rate:   ₱58.50 PHP per 1 USD
Taker Fee Rate:  0.10%
Notification:    ENABLED (Discord Webhook)
-------------------------------------------------------
Current Portfolio Balance:
 - PHP Cash:     ₱500,000.00 PHP
 - BTC Holdings: 0.000000 BTC
=======================================================
[2026-05-27 14:07:41 PHT] Connecting to Binance WebSocket stream at wss://stream.binance.com:9443/ws/btcusdt@kline_1m...
[2026-05-27 14:07:41 PHT] Fetching historical buffer candles to bootstrap indicators...
[2026-05-27 14:07:42 PHT] Loaded 150 buffer candles from exchange.
[2026-05-27 14:07:42 PHT] Connected! Listening for real-time ticks...
[2026-05-27 14:07:44 PHT] Tick: 2026-05-27 06:07:00 | BTC Price: $75,780.62 USD (₱4,433,166.27 PHP) | Closed: False
```

---

## Phase 7: Strategy Parameter Optimizer

We implemented a multi-dimensional grid search parameter optimizer in `optimize.py` to mathematically determine the best combinations for maximizing returns and Sharpe ratios while minimizing drawdowns.

###  Running the Optimizer
```bash
# Optimize the Crossover Strategy (sweeps Fast/Slow combinations + MA types)
./venv/bin/python3 optimize.py --strategy crossover --start 2025-01-01 --end 2025-12-31

# Optimize the RSI Strategy (sweeps RSI windows, oversold, and overbought levels)
./venv/bin/python3 optimize.py --strategy rsi --start 2025-01-01 --end 2025-12-31
```

###  Verification Sweep Outputs

#### 1. Crossover Strategy Sweep (158 combinations evaluated):
* **Rank 1 Combination:** Fast MA: 5, Slow MA: 40, Type: SMA
  * **Total Return:** **+22.74%**
  * **Sharpe Ratio:** 1.0824
  * **Max Drawdown:** 17.64%
  * **Win Rate:** 40.00% (5 trades total)
  * **Profit Factor:** 2.6311

#### 2. RSI Strategy Sweep (175 combinations evaluated):
* **Rank 1 Combination:** RSI Window: 16, Oversold threshold: 30, Overbought threshold: 75
  * **Total Return:** **+33.72%**
  * **Sharpe Ratio:** 1.1465
  * **Max Drawdown:** 19.04%
  * **Win Rate:** 100.00% (2 trades total)
  * **Profit Factor:** Infinity

All sweeps generate a complete grid results list saved directly to **[optimization_results.csv](file:///home/arvin/Project/btc-algo-trader/optimization_results.csv)** for further analysis.

---

## Phase 8: MACD Crossover Strategy

We implemented a new **Moving Average Convergence Divergence (MACD) Crossover Strategy** (`MACDStrategy`) across the entire algorithmic suite (backtesting CLI, optimizer, and live paper trading module).

###  Running MACD Backtest
```bash
./venv/bin/python3 main.py --strategy macd --start 2025-01-01 --end 2025-12-31
```
* **Performance Summary (Default 12/26/9 parameters):**
  * **Initial Capital:** $10,000.00 USDT
  * **Final Portfolio Value:** $8,081.05 USDT
  * **Total Return (%):** **-19.19%**
  * **Buy & Hold Return (%):** **-7.34%**
  * **Sharpe Ratio:** -0.6457
  * **Maximum Drawdown (%):** 24.96%
  * **Total Trades Executed:** 17
  * **Win Rate (%):** 23.53%
  * **Profit Factor:** 0.6018

###  Parameter Optimization for MACD (210 combinations evaluated)
```bash
./venv/bin/python3 optimize.py --strategy macd --start 2025-01-01 --end 2025-12-31
```
* **Rank 1 Combination:** Fast: 18, Slow: 32, Signal: 9
  * **Total Return:** **+6.36%** (outperformed Buy & Hold benchmark by 13.7%)
  * **Sharpe Ratio:** 0.3644
  * **Max Drawdown:** 21.35%
  * **Trades Executed:** 10
  * **Win Rate:** 30.00%
  * **Profit Factor:** 1.185

---

## Phase 9: Strategy Simulation & Ensemble Optimization

To minimize losses and maximize profit, we implemented a comprehensive simulation suite (`optimize_backtests.py`) testing SMA/EMA crossovers, RSI, MACD, and Ensemble rules against different Stop-Loss (SL) and Take-Profit (TP) boundaries, and integrated these risk controls across all offline and live execution channels.

###  Simulation Outputs & Report
We backtested **980 combinations** on 2025 BTC daily candle data, saving full outputs to **[strategy_simulation_analysis.csv](file:///home/arvin/Project/btc-algo-trader/strategy_simulation_analysis.csv)**. Key findings were stored in **[analysis_results.md](file:///home/arvin/Project/btc-algo-trader/analysis_results.md)**.
* **Winner Strategy:** `SMA_Cross_20_50` with a **1% Stop-Loss** and **3% Take-Profit**.
* **Metrics:** **+29.40% Return** (outperforming Buy & Hold by **+36.74%**), **2.1178 Sharpe Ratio**, and a **Max Drawdown of 5.84%**.

### ️ Key Technical Enhancements
1. **Engine Risk Controls ([simulator.py](file:///home/arvin/Project/btc-algo-trader/engine/simulator.py))**:
   - Integrates `stop_loss_pct` and `take_profit_pct` check directly inside the transaction loop, executing automatic risk liquidations and flagging them as `Stop Loss` or `Take Profit` in trade logs.
2. **Integrated Ensemble Strategy ([simple.py](file:///home/arvin/Project/btc-algo-trader/strategies/simple.py))**:
   - Built `EnsembleStrategy` supporting three modes: `macd_rsi` filter, `ema_rsi` filter, and `triple` indicator consensus.
3. **Live Auto-Liquidation & Alert system ([executor.py](file:///home/arvin/Project/btc-algo-trader/live/executor.py))**:
   - Intercepts live signals by checking the database entry price against active stop-loss/take-profit parameters. 
   - Triggers an instant market sell-off upon breaches and pushes specialized Discord embeds styled in Red (` STOP LOSS TRIGGERED`) or Orange/Gold (` TAKE PROFIT TRIGGERED`).

###  Running the Recommended Loss-Minimizer Strategy
* **Offline Backtest:**
  ```bash
  ./venv/bin/python3 main.py --strategy crossover --fast-window 20 --slow-window 50 --stop-loss 0.01 --take-profit 0.03 --start 2025-01-01 --end 2025-12-31
  ```
* **Live Paper Trading:**
  ```bash
  ./venv/bin/python3 main_live.py --strategy crossover --fast-window 20 --slow-window 50 --stop-loss 0.01 --take-profit 0.03 --timeframe 1m
  ```

---

## Phase 10: Glassmorphic Web Dashboard

We designed and built a premium web-based tracking dashboard running on **FastAPI** and styled with a custom responsive **Vanilla CSS glassmorphic** layout. 

### ️ Key Dashboard Features
1. **Real-Time Streaming (`/ws`)**: Uses a WebSocket connection to stream price updates, portfolio valuations, and active position indicators to the browser every 2 seconds.
2. **Interactive Charting (Chart.js)**:
   - **Equity Curve Line Chart**: Plots running PHP balance over time based on closed trade results.
   - **Asset Allocation Doughnut Chart**: Shows real-time weighting of Cash PHP vs active BTC value.
3. **Responsive Glassmorphism Styling**: Uses blur backdrops, radial gradients, glowing card grids, hover animations, and custom action badges.
4. **Live Trade Log Data Table**: Renders entries, exits, trade sizing, profit percentages, fee metrics, and status cards dynamically.

###  Running the Web Dashboard
* Start the server (default port `8000`):
  ```bash
  ./venv/bin/uvicorn web.app:app --host 0.0.0.0 --port 8000
  ```
* Open the browser: `http://localhost:8000`

---

## Phase 11: 1-Hour Intraday Optimization & Strategy Switch

After observing the 1-minute Crossover strategy losing money in live paper trading due to frequent whipsaws and fee drag, we pivoted to a data-driven approach: downloading 6 months of historical 1-hour candle data and running a comprehensive optimization sweep to find the best intraday strategy.

### ️ Infrastructure Changes
1. **CLI-Configurable Deep Sweep ([optimize_backtests.py](file:///home/arvin/Project/btc-algo-trader/optimize_backtests.py))**:
   - Added `argparse` support for `--timeframe`, `--start`, `--end`, `--capital`, `--fee`, and `--output` parameters.
   - Previously hardcoded to daily 2025 data; now supports any timeframe and date range.

###  1-Hour Sweep Results (910 Configurations)
We tested all strategy families (Crossover, RSI, MACD, Ensemble) × Stop-Loss/Take-Profit combinations against **4,345 hourly candles** from Nov 27, 2025 to May 27, 2026.

**Market context:** BTC dropped from $90,485 to $76,085 during this period (**-15.92% Buy & Hold**, **-35.59% Max Drawdown**).

| Strategy Family | Best Return | Best Sharpe | Verdict |
|---|---|---|---|
| **RSI (14, 30, 75)** | **+9.83%** | **0.1482** |  **Only profitable family** |
| SMA Crossover (20/50) | -6.72% | -0.074 |  Whipsaw losses |
| MACD (12/26/9) | -11.16% | -0.132 |  Trend-following fails in bear market |
| Ensemble (MACD+RSI) | -14.19% | -0.203 |  Over-trading at high frequency |

**Winner:** `RSI_14_OS30_OB75` with **3% Stop-Loss** and **10% Take-Profit** — returned **+9.83%** while the benchmark lost **-15.92%**, outperforming by **+25.75%**.

Full results saved to **[hourly_simulation_analysis.csv](file:///home/arvin/Project/btc-algo-trader/hourly_simulation_analysis.csv)**.

###  Live Bot Switch
Stopped the 1-minute SMA Crossover bot and started the optimized 1-hour RSI bot:
```bash
./venv/bin/python3 main_live.py --strategy rsi --rsi-window 14 --rsi-oversold 30 --rsi-overbought 75 --stop-loss 0.03 --take-profit 0.10 --timeframe 1h
```

###  Key Intraday Findings
1. **Mean-reversion (RSI) beats trend-following in bear/sideways markets.** Crossover strategies generate excessive false signals on noisy 1-hour data.
2. **Wider stop-losses are critical for intraday.** A 1% SL gets stopped out by normal hourly wicks; 3% SL gives enough room to survive noise while still protecting capital.
3. **Take-Profit of 10% captures full hourly swing moves** rather than exiting too early with 3%.

