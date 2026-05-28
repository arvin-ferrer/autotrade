import argparse
import itertools
import sys
import pandas as pd
from tabulate import tabulate

from data.loader import get_ohlcv
from strategies import CrossoverStrategy, RSIStrategy, MACDStrategy, VolumeRSIStrategy
from engine import Backtester, calculate_performance_metrics

def parse_args():
    parser = argparse.ArgumentParser(description="Bitcoin Strategy Parameter Optimization Tool")
    
    # Core settings
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help="Ticker symbol (default: BTC/USDT)")
    parser.add_argument('--timeframe', type=str, default='1d', help="Candle timeframe (e.g., 1d, 1h) (default: 1d)")
    parser.add_argument('--start', type=str, default='2025-01-01', help="Start date (default: 2025-01-01)")
    parser.add_argument('--end', type=str, default='2025-12-31', help="End date (default: 2025-12-31)")
    parser.add_argument('--strategy', type=str, default='crossover', choices=['crossover', 'rsi', 'macd', 'volumersi'], 
                        help="Strategy to optimize (default: crossover)")
    
    # Capital & Fee settings
    parser.add_argument('--capital', type=float, default=10000.0, help="Initial capital (default: 10000.0)")
    parser.add_argument('--fee', type=float, default=0.001, help="Transaction fee rate (default: 0.001)")
    
    # Optimization settings
    parser.add_argument('--sort-by', type=str, default='sharpe', choices=['return', 'sharpe', 'drawdown'], 
                        help="Metric to sort top results by (default: sharpe)")
    parser.add_argument('--top-n', type=int, default=10, help="Number of top results to display (default: 10)")
    parser.add_argument('--output', type=str, default='optimization_results.csv', 
                        help="CSV filename to save all results (default: optimization_results.csv)")
    
    return parser.parse_args()

def generate_crossover_grid():
    # Grid search boundaries
    fast_windows = list(range(5, 45, 5))    # 5, 10, 15, 20, 25, 30, 35, 40
    slow_windows = list(range(20, 130, 10)) # 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120
    ma_types = ['sma', 'ema']
    
    combinations = []
    for fast, slow, ma in itertools.product(fast_windows, slow_windows, ma_types):
        if fast < slow:
            combinations.append({
                'fast_window': fast,
                'slow_window': slow,
                'ma_type': ma
            })
    return combinations

def generate_rsi_grid():
    # Grid search boundaries
    rsi_windows = list(range(8, 22, 2))       # 8, 10, 12, 14, 16, 18, 20
    rsi_oversolds = list(range(20, 45, 5))    # 20, 25, 30, 35, 40
    rsi_overboughts = list(range(60, 85, 5))  # 60, 65, 70, 75, 80
    
    combinations = []
    for window, oversold, overbought in itertools.product(rsi_windows, rsi_oversolds, rsi_overboughts):
        combinations.append({
            'window': window,
            'oversold': oversold,
            'overbought': overbought
        })
    return combinations

def generate_volumersi_grid():
    # Fixed RSI parameters (based on previous optimization)
    rsi_windows = [14]
    rsi_oversolds = [30, 35]
    rsi_overboughts = [70, 75]
    
    # Volume filter parameters
    vol_ma_windows = [10, 20, 30]
    vol_multipliers = [1.2, 1.5, 2.0, 2.5]
    
    combinations = []
    for w, os, ob, v_ma, v_mult in itertools.product(rsi_windows, rsi_oversolds, rsi_overboughts, vol_ma_windows, vol_multipliers):
        combinations.append({
            'rsi_window': w,
            'oversold': os,
            'overbought': ob,
            'vol_ma_window': v_ma,
            'vol_multiplier': v_mult
        })
    return combinations

def generate_macd_grid():
    # Grid search boundaries
    fast_periods = list(range(8, 20, 2))      # 8, 10, 12, 14, 16, 18
    slow_periods = list(range(20, 34, 2))     # 20, 22, 24, 26, 28, 30, 32
    signal_periods = list(range(7, 12, 1))    # 7, 8, 9, 10, 11
    
    combinations = []
    for fast, slow, sig in itertools.product(fast_periods, slow_periods, signal_periods):
        if fast < slow:
            combinations.append({
                'fast_period': fast,
                'slow_period': slow,
                'signal_period': sig
            })
    return combinations

def main():
    args = parse_args()
    
    print("\n=======================================================")
    print("        STRATEGY PARAMETER OPTIMIZATION RUNNER         ")
    print("=======================================================")
    print(f"Symbol:        {args.symbol}")
    print(f"Timeframe:     {args.timeframe}")
    print(f"Date Range:    {args.start} to {args.end}")
    print(f"Strategy:      {args.strategy.upper()}")
    print(f"Sort Priority: {args.sort_by.upper()}")
    print("=======================================================\n")
    
    # 1. Fetch data once to reuse across backtests
    print("Fetching historical price dataset...")
    try:
        df = get_ohlcv(args.symbol, args.timeframe, args.start, args.end)
    except Exception as e:
        print(f"Error fetching data: {e}", file=sys.stderr)
        sys.exit(1)
        
    if df.empty:
        print("Data is empty. Exiting.", file=sys.stderr)
        sys.exit(1)
        
    # 2. Generate Parameter combinations
    if args.strategy == 'crossover':
        grid = generate_crossover_grid()
    elif args.strategy == 'rsi':
        grid = generate_rsi_grid()
    elif args.strategy == 'volumersi':
        grid = generate_volumersi_grid()
    else: # macd
        grid = generate_macd_grid()
        
    total_runs = len(grid)
    print(f"Generated {total_runs} parameter combinations to evaluate. Running optimization sweep...")
    
    results = []
    
    # 3. Optimization Loop
    for idx, params in enumerate(grid, 1):
        # Progress indicator
        sys.stdout.write(f"\rEvaluating combination {idx}/{total_runs}...")
        sys.stdout.flush()
        
        # Instantiate strategy
        if args.strategy == 'crossover':
            strategy = CrossoverStrategy(name="Temp_Crossover", params=params)
        elif args.strategy == 'rsi':
            strategy = RSIStrategy(name="Temp_RSI", params=params)
        elif args.strategy == 'volumersi':
            strategy = VolumeRSIStrategy(name="Temp_VolumeRSI", params=params)
        else: # macd
            strategy = MACDStrategy(name="Temp_MACD", params=params)
            
        try:
            # Generate signals
            df_signals = strategy.generate_signals(df)
            
            # Run backtest
            backtester = Backtester(initial_capital=args.capital, fee_rate=args.fee, slippage_rate=0.0)
            history_df, trades = backtester.run(df_signals)
            
            # Calculate metrics
            metrics = calculate_performance_metrics(history_df, trades, args.capital)
            
            # Save results
            res_entry = {**params}
            res_entry['total_return_pct'] = metrics['total_return_pct']
            res_entry['annualized_return_pct'] = metrics['annualized_return_pct']
            res_entry['sharpe_ratio'] = metrics['sharpe_ratio']
            res_entry['max_drawdown_pct'] = metrics['max_drawdown_pct']
            res_entry['total_trades'] = metrics['total_trades']
            res_entry['win_rate_pct'] = metrics['win_rate_pct']
            res_entry['profit_factor'] = metrics['profit_factor']
            results.append(res_entry)
            
        except Exception as e:
            # Continue on error, but record the exception details
            continue
            
    print("\nSweep completed! Formatting and sorting results...")
    
    if not results:
        print("Error: No successful backtest runs were completed.", file=sys.stderr)
        sys.exit(1)
        
    # 4. Process Results DataFrame
    results_df = pd.DataFrame(results)
    
    # Sort Priority mapping
    sort_columns = {
        'return': 'total_return_pct',
        'sharpe': 'sharpe_ratio',
        'drawdown': 'max_drawdown_pct'
    }
    
    sort_col = sort_columns[args.sort_by]
    ascending = True if args.sort_by == 'drawdown' else False
    
    # Sort and slice top N
    top_results_df = results_df.sort_values(by=sort_col, ascending=ascending)
    
    # Save full grid search results to CSV
    results_df.to_csv(args.output, index=False)
    print(f"Saved all {len(results_df)} sweep results to: {args.output}")
    
    # 5. Display Top Results Table
    print(f"\n--- TOP {args.top_n} STRATEGY PARAMETERS (Sorted by {args.sort_by.upper()}) ---")
    
    table_rows = []
    for rank, (_, row) in enumerate(top_results_df.head(args.top_n).iterrows(), 1):
        # Format parameters based on strategy type
        if args.strategy == 'crossover':
            params_str = f"Fast MA: {int(row['fast_window'])}, Slow MA: {int(row['slow_window'])}, Type: {row['ma_type'].upper()}"
        elif args.strategy == 'rsi':
            params_str = f"RSI: {int(row['window'])}, Oversold: {int(row['oversold'])}, Overbought: {int(row['overbought'])}"
        elif args.strategy == 'volumersi':
            params_str = f"Vol MA: {int(row['vol_ma_window'])}, Mult: {row['vol_multiplier']:.1f}x, RSI: OS{int(row['oversold'])}/OB{int(row['overbought'])}"
        else: # macd
            params_str = f"Fast: {int(row['fast_period'])}, Slow: {int(row['slow_period'])}, Signal: {int(row['signal_period'])}"
            
        # Handle inf values for profit factor display
        pf_val = row['profit_factor']
        pf_str = "inf" if pf_val == float('inf') else f"{pf_val:.4f}"
            
        table_rows.append([
            rank,
            params_str,
            f"{row['total_return_pct']:+,.2f}%",
            f"{row['sharpe_ratio']:.4f}",
            f"{row['max_drawdown_pct']:.2f}%",
            int(row['total_trades']),
            f"{row['win_rate_pct']:.2f}%",
            pf_str
        ])
        
    headers = ["Rank", "Parameters", "Total Return", "Sharpe", "Max Drawdown", "Trades", "Win Rate", "Profit Factor"]
    print(tabulate(table_rows, headers=headers, tablefmt="fancy_grid"))
    print("\n=======================================================")
    print("              OPTIMIZATION RUN COMPLETED               ")
    print("=======================================================\n")

if __name__ == '__main__':
    main()
