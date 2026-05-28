# Autonomous Strategy Evolution Loop (Quant-Ratchet)

We will build an autonomous quantitative research loop inspired by `karpathy/autoresearch` for the Bitcoin algorithmic trading bot. The framework will allow an AI agent to write Python strategy code, run backtests, parse performance metrics, and use Git to commit improvements and revert regressions.

## User Review Required

> [!IMPORTANT]
> **LLM API Integration:** The autonomous loop requires access to an LLM API to generate code proposals. We suggest using the **Google Gemini API** (via the `google-genai` library) using your existing local `GEMINI_API_KEY` environment variable.
> 
> **Data Splitting (Overfitting Guard):** To prevent the AI from overfitting to historical data, the evaluator will split data into:
> * **In-Sample (Train):** 70% of the data (used by the AI to optimize strategy rules).
> * **Out-of-Sample (Validation):** 30% of the data (used as a final check. If the strategy gains on Train but loses dramatically on Validation, it is discarded).

## Open Questions

> [!WARNING]
> 1. **LLM Provider:** Do you want to use the **Google Gemini API** (recommended, since it has a generous free tier / low latency) or **Anthropic Claude API**?
> 2. **Max Drawdown Limit:** What is the maximum acceptable peak-to-trough drawdown for any evolved strategy? We propose a limit of **15.0%**. If a strategy exceeds this, it is disqualified.
> 3. **Validation Threshold:** Should a strategy be accepted if it has a positive return on In-Sample but a slightly negative return on Validation, or must it be profitable on *both* segments?

---

## Proposed Changes

We will create/modify the following files to support the research framework:

### 1. Root Configuration & Dependencies
#### [MODIFY] [requirements.txt](file:///home/arvin/Project/btc-algo-trader/requirements.txt)
* Add `google-genai` or `anthropic` client libraries.

### 2. Research Orchestrator & Evaluator
#### [NEW] [research/evaluator.py](file:///home/arvin/Project/btc-algo-trader/research/evaluator.py)
* A standalone execution tool that:
  1. Loads `EvolvedStrategy` from `strategies/evolved.py`.
  2. Splits the historical dataset (e.g., 1-hour candles) into In-Sample and Out-of-Sample periods.
  3. Runs the backtester on both periods.
  4. Computes performance metrics (Sharpe Ratio, Return, Max Drawdown, Profit Factor, Win Rate, Trade Count).
  5. Computes a complexity penalty (e.g., penalizing strategies with > 200 lines of code to encourage simplicity).
  6. Outputs a standardized JSON structure representing the research results.

#### [NEW] [research/runner.py](file:///home/arvin/Project/btc-algo-trader/research/runner.py)
* The autonomous loop controller that:
  1. Reads the system instructions and goals from `research/program.md`.
  2. Calls the LLM API, providing the current codebase state, `strategies/evolved.py` contents, and previous evaluation results.
  3. Extracts the new Python code proposal and writes it to `strategies/evolved.py`.
  4. Executes `research/evaluator.py` in a subprocess.
  5. Evaluates the resulting metrics:
     * If the In-Sample Sharpe Ratio improves, validation metrics are acceptable, and code is clean, it runs `git commit -am "experiment: Sharpe improved to [X] on Train"` and appends details to `research/results.tsv`.
     * Otherwise, it runs `git checkout -- strategies/evolved.py` to revert changes.
  6. Repeats the loop for `N` iterations.

#### [NEW] [research/program.md](file:///home/arvin/Project/btc-algo-trader/research/program.md)
* The system instructions for the LLM agent, outlining:
  * Coding rules: must inherit from `BaseStrategy`, implement `generate_signals(df)`, and avoid external dependencies.
  * Research suggestions: using moving averages, RSI, Bollinger Bands, ATR, ADX, MACD, candlestick patterns, or volume analysis.
  * Rules for risk management: stop losses, take profits, dynamic trailing stops.

#### [NEW] [research/results.tsv](file:///home/arvin/Project/btc-algo-trader/research/results.tsv)
* A tab-separated file documenting the history of all accepted experiments (e.g., Timestamp, Commit Hash, Train Sharpe, Validation Sharpe, Train Return, Validation Return, Drawdown, Change Description).

### 3. Strategy Framework
#### [NEW] [strategies/evolved.py](file:///home/arvin/Project/btc-algo-trader/strategies/evolved.py)
* The strategy file targeted by the AI agent. Initialized with a basic RSI/SMA baseline strategy.

#### [MODIFY] [strategies/__init__.py](file:///home/arvin/Project/btc-algo-trader/strategies/__init__.py)
* Import and expose `EvolvedStrategy` so that the backtester and dashboard can load it dynamically.

---

## Verification Plan

### Automated Tests
1. Verify the evaluator executes correctly:
   ```bash
   python3 -m research.evaluator
   ```
   Check that it outputs valid JSON and runs the backtests on both training and validation sets without error.
2. Verify the registry:
   Ensure `EvolvedStrategy` is imported correctly in `strategies/__init__.py`.

### Manual Verification
1. Run a 1-iteration test of the runner:
   ```bash
   python3 -m research.runner --iterations 1
   ```
   Inspect the logs to verify that the LLM was called, the code was updated, the evaluator ran, and git successfully committed or reverted the result based on performance.
