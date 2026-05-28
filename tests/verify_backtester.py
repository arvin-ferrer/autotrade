import os
import pandas as pd
import numpy as np
from tabulate import tabulate

from data.loader import get_ohlcv
from strategies import CrossoverStrategy
from engine import Backtester, calculate_performance_metrics

def main():
    print("=== STARTING BACKTESTER VERIFICATION ===\n")
    
    # 1. Load data and generate signals
    symbol = 'BTC/USDT'
    timeframe = '1d'
    start_date = '2026-04-01'
    end_date = '2026-05-25'
    
    print(f"Loading cached BTC data ({symbol}, {timeframe}) from {start_date} to {end_date}...")
    df = get_ohlcv(symbol, timeframe, start_date, end_date)
    print(f"Loaded {len(df)} candles.\n")
    
    # Generate SMA crossover signals
    crossover_sma = CrossoverStrategy(name="SMA_Crossover", params={'fast_window': 20, 'slow_window': 50, 'ma_type': 'sma'})
    df_sma = crossover_sma.generate_signals(df)
    
    # 2. Run Backtester
    print("Running Backtester (initial_capital=10000, fee_rate=0.001, slippage_rate=0.0)...")
    backtester = Backtester(initial_capital=10000.0, fee_rate=0.001, slippage_rate=0.0)
    history_df, trades = backtester.run(df_sma)
    
    print(f"Backtest completed. Number of trades: {len(trades)}\n")
    
    # Print Trades Log
    if trades:
        print("--- TRADES LOG ---")
        trade_rows = []
        for i, t in enumerate(trades):
            trade_rows.append([
                i + 1,
                t['entry_date'].strftime('%Y-%m-%d') if hasattr(t['entry_date'], 'strftime') else str(t['entry_date']),
                t['exit_date'].strftime('%Y-%m-%d') if hasattr(t['exit_date'], 'strftime') else str(t['exit_date']),
                f"${t['entry_price']:.2f}",
                f"${t['exit_price']:.2f}",
                f"{t['size']:.6f} BTC",
                f"${t['profit']:.2f}",
                f"{t['return_pct']:.2f}%",
                f"${t['fee']:.2f}"
            ])
        headers = ["#", "Entry Date", "Exit Date", "Entry Price", "Exit Price", "Size", "Profit", "Return %", "Total Fee"]
        print(tabulate(trade_rows, headers=headers, tablefmt="grid"))
        print()
    else:
        print("No trades executed during the backtest period.\n")
        
    # Print last 10 rows of history
    print("--- DAILY PORTFOLIO HISTORY (Last 10 Days) ---")
    history_rows = []
    for idx, row in history_df.tail(10).iterrows():
        history_rows.append([
            idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx),
            f"${row['Cash']:.2f}",
            f"{row['Holdings']:.6f} BTC",
            f"${row['Asset_Value']:.2f}",
            f"${row['Total_Value']:.2f}",
            f"${row['Close']:.2f}"
        ])
    history_headers = ["Date", "Cash", "Holdings", "Asset Value", "Total Value", "Close Price"]
    print(tabulate(history_rows, headers=history_headers, tablefmt="grid"))
    print()
    
    # 3. Calculate Performance Metrics
    print("Calculating Performance Metrics...")
    metrics = calculate_performance_metrics(history_df, trades, initial_capital=10000.0)
    
    metrics_rows = [
        ["Initial Capital", f"${metrics['initial_value']:.2f}"],
        ["Final Portfolio Value", f"${metrics['final_value']:.2f}"],
        ["Total Return (%)", f"{metrics['total_return_pct']:.2f}%"],
        ["Annualized Return (%)", f"{metrics['annualized_return_pct']:.2f}%"],
        ["Buy & Hold Return (%)", f"{metrics['buy_and_hold_return_pct']:.2f}%"],
        ["Sharpe Ratio", f"{metrics['sharpe_ratio']:.4f}"],
        ["Max Drawdown (%)", f"{metrics['max_drawdown_pct']:.2f}%"],
        ["Total Trades Executed", metrics['total_trades']],
        ["Win Rate (%)", f"{metrics['win_rate_pct']:.2f}%"],
        ["Profit Factor", f"{metrics['profit_factor']:.4f}"]
    ]
    print(tabulate(metrics_rows, headers=["Metric", "Value"], tablefmt="grid"))
    print()
    
    # 4. Test Edge Cases
    print("=== TESTING EDGE CASES ===")
    
    # Empty DataFrame
    print("Testing empty DataFrame...")
    empty_df = pd.DataFrame(columns=['Close', 'Signal'])
    empty_df.index = pd.to_datetime([], utc=True)
    hist_empty, trades_empty = backtester.run(empty_df)
    assert hist_empty.empty
    assert len(trades_empty) == 0
    metrics_empty = calculate_performance_metrics(hist_empty, trades_empty, 10000.0)
    assert metrics_empty['total_trades'] == 0
    assert metrics_empty['win_rate_pct'] == 0.0
    assert metrics_empty['profit_factor'] == 0.0
    print("Empty DataFrame test: PASSED.")
    
    # Zero trades
    print("Testing zero trades performance metrics calculations...")
    metrics_no_trades = calculate_performance_metrics(history_df, [], 10000.0)
    assert metrics_no_trades['total_trades'] == 0
    assert metrics_no_trades['win_rate_pct'] == 0.0
    assert metrics_no_trades['profit_factor'] == 0.0
    print("Zero trades test: PASSED.")
    
    # Non-zero slippage test
    print("Testing non-zero slippage (slippage_rate = 0.001)...")
    backtester_slip = Backtester(initial_capital=10000.0, fee_rate=0.001, slippage_rate=0.001)
    history_slip, trades_slip = backtester_slip.run(df_sma)
    print(f"Number of trades with slippage: {len(trades_slip)}")
    if len(trades_slip) > 0 and len(trades) > 0:
        # Check that entry price is higher with slippage (since it's a buy)
        print(f"No slippage entry: ${trades[0]['entry_price']:.2f}, Slippage entry: ${trades_slip[0]['entry_price']:.2f}")
        assert trades_slip[0]['entry_price'] > trades[0]['entry_price']
        print(f"No slippage exit: ${trades[0]['exit_price']:.2f}, Slippage exit: ${trades_slip[0]['exit_price']:.2f}")
        assert trades_slip[0]['exit_price'] < trades[0]['exit_price']
        print(f"No slippage size: {trades[0]['size']:.6f}, Slippage size: {trades_slip[0]['size']:.6f}")
        assert trades_slip[0]['size'] < trades[0]['size']
    print("Slippage test: PASSED.")
    
    print("\n=== ALL VERIFICATIONS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    main()
