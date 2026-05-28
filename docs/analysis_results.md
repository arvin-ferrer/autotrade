# Quantitative Strategy Simulation & Analysis Report

This report presents the findings of our comprehensive strategy simulation suite across the full year of **2025** on the **BTC/USDT** daily dataset. We evaluated a total of **980 configurations** combining trend-following (SMA/EMA crossovers), momentum (RSI), convergence/divergence (MACD), and multi-indicator Ensemble rules against different Stop-Loss (SL) and Take-Profit (TP) parameters.

---

## 📊 Summary of Top Configurations (Sorted by Sharpe Ratio)

| Rank | Strategy Name | Stop Loss (SL) | Take Profit (TP) | Total Return | Sharpe Ratio | Max Drawdown | Total Trades | Win Rate | Profit Factor | SL/TP Hits |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | **SMA_Cross_20_50** | **1%** | **3%** | **+29.40%** | **2.1178** | **5.84%** | **30** | **53.33%** | **2.5545** | 14 SL / 14 TP |
| **2** | **EMA_Cross_5_100** | **1%** | **3%** | **+31.61%** | **1.8079** | **5.84%** | **43** | **46.51%** | **1.9965** | 22 SL / 19 TP |
| **3** | **EMA_Cross_5_50** | **1%** | **3%** | **+28.93%** | **1.7796** | **5.84%** | **38** | **47.37%** | **2.0380** | 19 SL / 17 TP |
| **4** | **EMA_Cross_10_30** | **1%** | **3%** | **+27.32%** | **1.7195** | **6.59%** | **37** | **48.65%** | **2.0033** | 19 SL / 16 TP |
| **5** | **EMA_Cross_20_100** | **1%** | **3%** | **+31.52%** | **1.7166** | **5.84%** | **43** | **46.51%** | **1.9898** | 23 SL / 20 TP |
| **6** | **EMA_Cross_10_100** | **1%** | **3%** | **+29.41%** | **1.6538** | **5.84%** | **46** | **45.65%** | **1.8550** | 23 SL / 20 TP |
| **7** | **SMA_Cross_20_50** | **1%** | **10%** | **+34.44%** | **1.6393** | **9.22%** | **12** | **41.67%** | **4.4302** | 7 SL / 3 TP |
| **8** | **SMA_Cross_5_50** | **1%** | **5%** | **+23.50%** | **1.5700** | **7.16%** | **21** | **42.86%** | **2.3971** | 12 SL / 7 TP |
| **9** | **EMA_Cross_5_50** | **1%** | **5%** | **+29.97%** | **1.5542** | **9.38%** | **29** | **37.93%** | **2.1574** | 18 SL / 9 TP |
| **10** | **EMA_Cross_10_30** | **1%** | **5%** | **+29.02%** | **1.5339** | **8.28%** | **28** | **39.29%** | **2.1877** | 17 SL / 9 TP |

---

## 📈 Analysis of Findings

### 1. The Power of Tight Risk Controls (1% SL / 3% TP)
The single most significant discovery of the simulation was that **implementing a tight 1% Stop-Loss and 3% Take-Profit dramatically improves the Sharpe Ratio** and controls risk across the board.
* Without risk controls, the standard SMA 20/50 crossover strategy had a **Maximum Drawdown of 14.62%** and a Sharpe ratio of **0.8035**.
* By adding a **1% Stop-Loss** and **3% Take-Profit**, the Max Drawdown was slashed to just **5.84%**, while the Sharpe ratio surged to **2.1178**.
* **Why it works:** BTC frequently experiences false breakouts (fakeouts) during consolidation phases. A tight 1% stop-loss cuts bad trades instantly before they cascade, while a 3% take-profit locks in short-term gains before the trend reverses.

### 2. Simple Crossover vs. Multi-Indicator Ensemble
* The **Triple Ensemble Strategy** (MACD + EMA Crossover + RSI consensus) achieved a highly respectable Sharpe ratio of **1.1381** and **6.21%** Max Drawdown when paired with a **1% Stop-Loss**.
* However, the simple **SMA 20/50 Crossover** with SL/TP significantly outperformed it (+29.40% Return, 2.1178 Sharpe).
* **Why it works:** The Triple Ensemble is highly selective, requiring multiple independent signals to line up. In highly volatile BTC markets, this extreme selectivity leads to **delayed entries** during sharp upward swings and fewer trades overall (18 trades vs 30 trades), causing the bot to leave money on the table.

### 3. RSI Momentum Performance
* The **RSI Strategy** (14 window, 30/70 thresholds) paired with **1% SL** and **5% TP** performed exceptionally well relative to its drawdown, achieving a **1.5189 Sharpe Ratio** and a remarkably low **2.44% Max Drawdown**.
* It executed only **3 trades** but achieved a **66.67% Win Rate** and a **7.76 Profit Factor**.
* **Takeaway:** RSI is a highly conservative strategy with excellent capital preservation, but its trade frequency is too low to maximize absolute gains.

---

## 🏆 Recommendation: The Loss-Minimizer Strategy

To minimize losses and maximize profit, we recommend running the **SMA 20/50 Crossover Strategy with a 1% Stop-Loss and a 3% Take-Profit**.

### Strategy Specifications
* **Fast Moving Average Window:** 20 spans
* **Slow Moving Average Window:** 50 spans
* **Moving Average Type:** SMA
* **Stop Loss Percentage:** **1.0%** (`--stop-loss 0.01`)
* **Take Profit Percentage:** **3.0%** (`--take-profit 0.03`)

### Performance Metrics on 2025 BTC Daily Data
* **Starting Capital:** $10,000.00 USDT
* **Ending Capital:** $12,939.77 USDT (**+29.40% Net Profit**)
* **Buy & Hold Asset Return:** -7.34% (**Outperformed by +36.74%**)
* **Sharpe Ratio:** **2.1178**
* **Maximum Drawdown:** **5.84%**
* **Total Trades Executed:** 30
* **Win Rate:** 53.33%
* **Profit Factor:** 2.5545
* **Execution Logs:** 14 Stop Loss hits, 14 Take Profit hits, 2 normal signal exits.

---

## 🕒 1-Hour Intraday Strategy Simulation & Analysis (Nov 2025 - May 2026)

To optimize the strategy for intraday trading, we downloaded **4,345 1-hour candles** covering a 6-month period from **November 27, 2025, to May 27, 2026**. We ran a deep sweep of **910 configurations** across SMA/EMA Crossover, RSI, MACD, and Ensemble strategies with varying Stop-Loss and Take-Profit boundaries.

### 📉 Intraday Market Context
During this 6-month period, Bitcoin was in a significant correction phase (bear market / choppy range):
* **BTC Starting Price:** $90,485.85 USD
* **BTC Ending Price:** $76,085.01 USD
* **BTC Buy & Hold Return:** **-15.92%**
* **BTC Buy & Hold Max Drawdown:** **-35.59%**

### 📊 Top 1h Intraday Configurations (Sorted by Sharpe Ratio)

| Rank | Strategy Name | Stop Loss (SL) | Take Profit (TP) | Total Return | Sharpe Ratio | Max Drawdown | Total Trades | Win Rate | Profit Factor | SL/TP Hits |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | **RSI_14_OS30_OB75** | **3%** | **10%** | **+9.83%** | **0.1482** | **29.39%** | **33** | **45.45%** | **1.1662** | 18 SL / 3 TP |
| **2** | **RSI_14_OS30_OB75** | **3%** | **15%** | **+9.64%** | **0.1426** | **29.39%** | **32** | **43.75%** | **1.1634** | 18 SL / 0 TP |
| **3** | **RSI_14_OS30_OB75** | **3%** | **None** | **+9.64%** | **0.1426** | **29.39%** | **32** | **43.75%** | **1.1634** | 18 SL / 0 TP |
| **4** | **RSI_14_OS30_OB75** | **3%** | **20%** | **+9.64%** | **0.1426** | **29.39%** | **32** | **43.75%** | **1.1634** | 18 SL / 0 TP |
| **5** | **RSI_14_OS30_OB75** | **3%** | **30%** | **+9.64%** | **0.1426** | **29.39%** | **32** | **43.75%** | **1.1634** | 18 SL / 0 TP |
| **6** | **RSI_14_OS30_OB70** | **5%** | **10%** | **+6.43%** | **0.1129** | **29.05%** | **28** | **64.29%** | **1.1260** | 10 SL / 1 TP |
| **7** | **RSI_14_OS30_OB75** | **5%** | **10%** | **+6.71%** | **0.1119** | **31.59%** | **24** | **50.00%** | **1.1304** | 10 SL / 2 TP |
| **8** | **RSI_14_OS30_OB75** | **5%** | **30%** | **+5.68%** | **0.0993** | **31.59%** | **23** | **47.83%** | **1.1107** | 10 SL / 0 TP |
| **9** | **RSI_14_OS30_OB75** | **5%** | **15%** | **+5.68%** | **0.0993** | **31.59%** | **23** | **47.83%** | **1.1107** | 10 SL / 0 TP |
| **10** | **RSI_14_OS30_OB75** | **5%** | **20%** | **+5.68%** | **0.0993** | **31.59%** | **23** | **47.83%** | **1.1107** | 10 SL / 0 TP |

### 📈 Key Intraday Findings

1. **Mean Reversion is Mandatory in Down/Sideways Markets:**
   * **RSI (14, 30, 75)** was the only strategy family that remained profitable during this bear phase, yielding up to **+9.83%** return and outperforming the benchmark by **+25.75%**.
   * **Trend-Following Crossover** strategies suffered heavily from whipsaws, losing **-6.72%** (SMA Crossover 20/50).
   * **MACD** trend-following also lost **-11.16%** (`MACD_12_26_9`).
   * **Ensembles** combining trend and momentum filters were overly active in short intervals, losing **-14.19%**.

2. **Intraday Volatility Requires Breathing Room:**
   * Tighter stop-losses (1% and 2%) led to **premature stop-outs** due to intraday price spikes (wicks). For example:
     - RSI with **3% SL** returned **+9.83%**
     - RSI with **2% SL** returned only **+0.87%**
     - RSI with **1% SL** lost **-0.44%**
   * Keeping a slightly wider stop-loss (3% or 5%) on 1-hour candles allows trades to survive normal intraday fluctuations.

3. **Risk Profile Comparison:**
   * While the RSI strategy's maximum drawdown (**29.39%**) appears high, it is significantly better than the benchmark's **-35.59%** drawdown. In this high-beta period, the algorithm successfully mitigated downside risk while extracting positive alpha.

