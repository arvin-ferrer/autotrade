import os
import sys
import itertools
import pandas as pd
import numpy as np
from tabulate import tabulate

from data.loader import get_ohlcv
from strategies import CrossoverStrategy, RSIStrategy, MACDStrategy, EnsembleStrategy, VolumeRSIStrategy
from engine import Backtester, calculate_performance_metrics

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Deep Strategy Simulation & Ensemble Sweep")
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help="Ticker symbol (default: BTC/USDT)")
    parser.add_argument('--timeframe', type=str, default='1d', help="Candle timeframe (e.g. 1d, 1h) (default: 1d)")
    parser.add_argument('--start', type=str, default='2025-01-01', help="Start date (default: 2025-01-01)")
    parser.add_argument('--end', type=str, default='2025-12-31', help="End date (default: 2025-12-31)")
    parser.add_argument('--capital', type=float, default=10000.0, help="Initial capital (default: 10000.0)")
    parser.add_argument('--fee', type=float, default=0.001, help="Fee rate (default: 0.001)")
    parser.add_argument('--output', type=str, default='strategy_simulation_analysis.csv', help="Output CSV path (default: strategy_simulation_analysis.csv)")
    args = parser.parse_args()

    print("\n=======================================================")
    print("      DEEP STRATEGY SIMULATION & ENSEMBLE SWEEP        ")
    print("=======================================================")
    print(f"Symbol:      {args.symbol}")
    print(f"Timeframe:   {args.timeframe}")
    print(f"Range:       {args.start} to {args.end}")
    print(f"Capital:     ${args.capital:,.2f} USD")
    print(f"Fees:        {args.fee * 100:.2f}% Taker")
    print("=======================================================\n")

    symbol = args.symbol
    timeframe = args.timeframe
    start_date = args.start
    end_date = args.end
    
    print("Fetching historical price dataset...")
    try:
        df = get_ohlcv(symbol, timeframe, start_date, end_date)
    except Exception as e:
        print(f"Error loading historical data: {e}", file=sys.stderr)
        sys.exit(1)
        
    if df.empty:
        print("Historical dataset is empty.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Loaded {len(df)} candles. Initializing simulation sweep combinations...")

    # Define optimization boundaries
    sl_options = [None, 0.01, 0.02, 0.03, 0.05]
    tp_options = [None, 0.03, 0.05, 0.10, 0.15, 0.20, 0.30]
    
    sweep_list = []

    # 1. Crossover Strategies Grid
    ma_types = ['sma', 'ema']
    fast_windows = [5, 10, 20]
    slow_windows = [30, 50, 100]
    for ma, fast, slow in itertools.product(ma_types, fast_windows, slow_windows):
        if fast < slow:
            sweep_list.append({
                'type': 'crossover',
                'strategy_class': CrossoverStrategy,
                'name': f"{ma.upper()}_Cross_{fast}_{slow}",
                'params': {'fast_window': fast, 'slow_window': slow, 'ma_type': ma}
            })

    # 2. RSI Strategies Grid
    rsi_windows = [14]
    rsi_oversolds = [30, 35]
    rsi_overboughts = [70, 75]
    for w, os_val, ob_val in itertools.product(rsi_windows, rsi_oversolds, rsi_overboughts):
        sweep_list.append({
            'type': 'rsi',
            'strategy_class': RSIStrategy,
            'name': f"RSI_{w}_OS{os_val}_OB{ob_val}",
            'params': {'window': w, 'oversold': os_val, 'overbought': ob_val}
        })

    # 2.5 Volume RSI Strategies Grid
    vol_ma_windows = [20, 30]
    vol_multipliers = [1.2, 1.5, 2.0]
    for w, os_val, ob_val, v_ma, v_mult in itertools.product(rsi_windows, rsi_oversolds, rsi_overboughts, vol_ma_windows, vol_multipliers):
        sweep_list.append({
            'type': 'volumersi',
            'strategy_class': VolumeRSIStrategy,
            'name': f"VolRSI_{w}_OS{os_val}_OB{ob_val}_V{v_ma}_M{v_mult}",
            'params': {
                'rsi_window': w, 
                'oversold': os_val, 
                'overbought': ob_val,
                'vol_ma_window': v_ma,
                'vol_multiplier': v_mult
            }
        })

    # 3. MACD Strategies Grid
    macd_fasts = [12]
    macd_slows = [26]
    macd_signals = [9]
    for f, s, sig in itertools.product(macd_fasts, macd_slows, macd_signals):
        sweep_list.append({
            'type': 'macd',
            'strategy_class': MACDStrategy,
            'name': f"MACD_{f}_{s}_{sig}",
            'params': {'fast_period': f, 'slow_period': s, 'signal_period': sig}
        })

    # 4. Ensemble Strategies Grid
    ensemble_rules = ['macd_rsi', 'ema_rsi', 'triple']
    for rule in ensemble_rules:
        sweep_list.append({
            'type': 'ensemble',
            'strategy_class': EnsembleStrategy,
            'name': f"Ensemble_{rule}",
            'params': {
                'fast_window': 20,
                'slow_window': 50,
                'ma_type': 'ema',
                'rsi_window': 14,
                'rsi_overbought': 70.0,
                'rsi_oversold': 30.0,
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'rules': rule
            }
        })

    # Create full matrix including SL/TP combinations
    full_combinations = list(itertools.product(sweep_list, sl_options, tp_options))
    total_runs = len(full_combinations)
    print(f"Generated {total_runs} simulation configurations to backtest...")

    results = []

    for idx, (strat_def, sl, tp) in enumerate(full_combinations, 1):
        if idx % 50 == 0 or idx == total_runs:
            sys.stdout.write(f"\rBacktesting configuration {idx}/{total_runs}...")
            sys.stdout.flush()

        # Instantiate strategy and generate signals
        strat = strat_def['strategy_class'](name=strat_def['name'], params=strat_def['params'])
        try:
            df_signals = strat.generate_signals(df)
            
            # Setup backtester with risk controls
            backtester = Backtester(
                initial_capital=args.capital,
                fee_rate=args.fee,
                slippage_rate=0.0,
                stop_loss_pct=sl,
                take_profit_pct=tp
            )
            
            history_df, trades = backtester.run(df_signals)
            metrics = calculate_performance_metrics(history_df, trades, args.capital)
            
            # Count exits by type
            sl_hits = sum(1 for t in trades if t.get('exit_reason') == 'Stop Loss')
            tp_hits = sum(1 for t in trades if t.get('exit_reason') == 'Take Profit')
            sig_exits = sum(1 for t in trades if t.get('exit_reason') == 'Signal')
            
            # Clean display settings
            sl_str = f"{int(sl*100)}%" if sl is not None else "None"
            tp_str = f"{int(tp*100)}%" if tp is not None else "None"
            
            results.append({
                'strategy_type': strat_def['type'],
                'strategy_name': strat_def['name'],
                'params_str': str(strat_def['params']),
                'stop_loss': sl_str,
                'take_profit': tp_str,
                'total_return_pct': metrics['total_return_pct'],
                'annualized_return_pct': metrics['annualized_return_pct'],
                'sharpe_ratio': metrics['sharpe_ratio'],
                'max_drawdown_pct': metrics['max_drawdown_pct'],
                'total_trades': metrics['total_trades'],
                'win_rate_pct': metrics['win_rate_pct'],
                'profit_factor': metrics['profit_factor'],
                'stop_loss_hits': sl_hits,
                'take_profit_hits': tp_hits,
                'signal_exits': sig_exits
            })
        except Exception as e:
            continue

    print("\nSweep completed! Formatting and sorting results...")

    if not results:
        print("Error: No simulations succeeded.", file=sys.stderr)
        sys.exit(1)

    results_df = pd.DataFrame(results)
    
    # Save sweep details to CSV
    output_csv = args.output
    results_df.to_csv(output_csv, index=False)
    print(f"Saved all {len(results_df)} sweep results to: {output_csv}")

    # Display Top 20 strategies sorted by Sharpe Ratio descending
    top_sharpe = results_df.sort_values(by='sharpe_ratio', ascending=False).head(20)
    
    print("\n" + "="*80)
    print("             TOP 20 OPTIMIZED STRATEGY CONFIGURATIONS (BY SHARPE)           ")
    print("="*80)
    
    table_rows = []
    for idx, (_, row) in enumerate(top_sharpe.iterrows(), 1):
        pf_val = row['profit_factor']
        pf_str = "inf" if pf_val == float('inf') else f"{pf_val:.4f}"
        
        table_rows.append([
            idx,
            row['strategy_name'],
            row['stop_loss'],
            row['take_profit'],
            f"{row['total_return_pct']:+,.2f}%",
            f"{row['sharpe_ratio']:.4f}",
            f"{row['max_drawdown_pct']:.2f}%",
            int(row['total_trades']),
            f"{row['win_rate_pct']:.2f}%",
            pf_str,
            f"{row['stop_loss_hits']}/{row['take_profit_hits']}"
        ])
        
    headers = ["Rank", "Strategy Name", "SL", "TP", "Return", "Sharpe", "Max DD", "Trades", "Win Rate", "Profit Factor", "SL/TP Hits"]
    print(tabulate(table_rows, headers=headers, tablefmt="fancy_grid"))
    
    print("\n" + "="*80)
    print("             TOP 10 STRATEGY CONFIGURATIONS (BY TOTAL RETURN)             ")
    print("="*80)
    top_return = results_df.sort_values(by='total_return_pct', ascending=False).head(10)
    table_return_rows = []
    for idx, (_, row) in enumerate(top_return.iterrows(), 1):
        pf_val = row['profit_factor']
        pf_str = "inf" if pf_val == float('inf') else f"{pf_val:.4f}"
        table_return_rows.append([
            idx,
            row['strategy_name'],
            row['stop_loss'],
            row['take_profit'],
            f"{row['total_return_pct']:+,.2f}%",
            f"{row['sharpe_ratio']:.4f}",
            f"{row['max_drawdown_pct']:.2f}%",
            int(row['total_trades']),
            f"{row['win_rate_pct']:.2f}%",
            pf_str
        ])
    print(tabulate(table_return_rows, headers=["Rank", "Strategy Name", "SL", "TP", "Return", "Sharpe", "Max DD", "Trades", "Win Rate", "Profit Factor"], tablefmt="fancy_grid"))
    print("\n=======================================================")
    print("               DEEP SWEEP COMPLETED                    ")
    print("=======================================================\n")

if __name__ == '__main__':
    main()
