import argparse
import sys
from tabulate import tabulate
import pandas as pd

from data.loader import get_ohlcv
from strategies import CrossoverStrategy, RSIStrategy, MACDStrategy, EnsembleStrategy
from engine import Backtester, calculate_performance_metrics
from utils import render_ascii_price_chart, plot_equity_curve

def parse_args():
    parser = argparse.ArgumentParser(description="Bitcoin Quantitative Algorithmic Backtesting CLI")
    
    # Core settings
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help="Trading symbol (default: BTC/USDT)")
    parser.add_argument('--timeframe', type=str, default='1d', help="Candle timeframe (e.g. 1d, 1h) (default: 1d)")
    parser.add_argument('--start', type=str, default='2025-01-01', help="Start date (YYYY-MM-DD) (default: 2025-01-01)")
    parser.add_argument('--end', type=str, default='2025-12-31', help="End date (YYYY-MM-DD) (default: 2025-12-31)")
    parser.add_argument('--strategy', type=str, default='crossover', choices=['crossover', 'rsi', 'macd', 'ensemble'], 
                        help="Trading strategy to execute (default: crossover)")
    
    # Portfolio & Risk settings
    parser.add_argument('--capital', type=float, default=10000.0, help="Initial account balance (default: 10000.0)")
    parser.add_argument('--fee', type=float, default=0.001, help="Transaction fee rate (e.g., 0.001 = 0.1%%) (default: 0.001)")
    parser.add_argument('--slippage', type=float, default=0.0, help="Slippage rate (e.g., 0.0005 = 0.05%%) (default: 0.0)")
    parser.add_argument('--stop-loss', type=float, default=None, help="Stop loss percentage as float (e.g., 0.02 = 2%%) (default: None)")
    parser.add_argument('--take-profit', type=float, default=None, help="Take profit percentage as float (e.g., 0.05 = 5%%) (default: None)")
    
    # Crossover strategy settings
    parser.add_argument('--fast-window', type=int, default=20, help="Fast moving average period (default: 20)")
    parser.add_argument('--slow-window', type=int, default=50, help="Slow moving average period (default: 50)")
    parser.add_argument('--ma-type', type=str, default='sma', choices=['sma', 'ema'], help="MA type: sma or ema (default: sma)")
    
    # RSI strategy settings
    parser.add_argument('--rsi-window', type=int, default=14, help="RSI calculation period (default: 14)")
    parser.add_argument('--rsi-overbought', type=float, default=70.0, help="RSI sell threshold (default: 70.0)")
    parser.add_argument('--rsi-oversold', type=float, default=30.0, help="RSI buy threshold (default: 30.0)")
    
    # MACD strategy settings
    parser.add_argument('--macd-fast', type=int, default=12, help="MACD fast EMA period (default: 12)")
    parser.add_argument('--macd-slow', type=int, default=26, help="MACD slow EMA period (default: 26)")
    parser.add_argument('--macd-signal', type=int, default=9, help="MACD signal EMA period (default: 9)")
    
    # Ensemble strategy settings
    parser.add_argument('--ensemble-rules', type=str, default='macd_rsi', choices=['macd_rsi', 'ema_rsi', 'triple'],
                        help="Ensemble decision rules (default: macd_rsi)")

    # Output settings
    parser.add_argument('--plot', type=str, default='equity_curve.png', help="Output filename for equity plot (default: equity_curve.png)")
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    print("\n=======================================================")
    print("      BITCOIN ALGORITHMIC BACKTESTING PLATFORM         ")
    print("=======================================================")
    print(f"Exchange:      Binance (via CCXT)")
    print(f"Symbol:        {args.symbol}")
    print(f"Timeframe:     {args.timeframe}")
    print(f"Date Range:    {args.start} to {args.end}")
    print(f"Strategy:      {args.strategy.upper()}")
    print(f"Capital:       ${args.capital:,.2f} USDT")
    print(f"Fee Rate:      {args.fee * 100:.2f}% (Taker)")
    print(f"Slippage:      {args.slippage * 100:.2f}%")
    print("=======================================================\n")
    
    # 1. Fetch data
    try:
        df = get_ohlcv(
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=args.start,
            end_date=args.end
        )
    except Exception as e:
        print(f"Fatal error fetching data: {e}", file=sys.stderr)
        sys.exit(1)
        
    if df.empty:
        print("No historical data fetched. Exiting.", file=sys.stderr)
        sys.exit(1)
        
    # 2. Instantiate and run strategy
    if args.strategy == 'crossover':
        params = {
            'fast_window': args.fast_window,
            'slow_window': args.slow_window,
            'ma_type': args.ma_type
        }
        strategy = CrossoverStrategy(name=f"{args.ma_type.upper()}_Crossover", params=params)
        print(f"Running strategy: {strategy.name} with Fast={args.fast_window}, Slow={args.slow_window}...")
    elif args.strategy == 'rsi':
        params = {
            'window': args.rsi_window,
            'overbought': args.rsi_overbought,
            'oversold': args.rsi_oversold
        }
        strategy = RSIStrategy(name="RSI_Momentum", params=params)
        print(f"Running strategy: {strategy.name} with Window={args.rsi_window}, Oversold={args.rsi_oversold}, Overbought={args.rsi_overbought}...")
    elif args.strategy == 'macd':
        params = {
            'fast_period': args.macd_fast,
            'slow_period': args.macd_slow,
            'signal_period': args.macd_signal
        }
        strategy = MACDStrategy(name="MACD_Crossover", params=params)
        print(f"Running strategy: {strategy.name} with Fast={args.macd_fast}, Slow={args.macd_slow}, Signal={args.macd_signal}...")
    else: # ensemble
        params = {
            'fast_window': args.fast_window,
            'slow_window': args.slow_window,
            'ma_type': args.ma_type,
            'rsi_window': args.rsi_window,
            'rsi_overbought': args.rsi_overbought,
            'rsi_oversold': args.rsi_oversold,
            'macd_fast': args.macd_fast,
            'macd_slow': args.macd_slow,
            'macd_signal': args.macd_signal,
            'rules': args.ensemble_rules
        }
        strategy = EnsembleStrategy(name=f"Ensemble_{args.ensemble_rules}", params=params)
        print(f"Running strategy: {strategy.name} with Rules={args.ensemble_rules}...")
        
    df_signals = strategy.generate_signals(df)
    
    # 3. Initialize and run Backtester
    backtester = Backtester(
        initial_capital=args.capital,
        fee_rate=args.fee,
        slippage_rate=args.slippage,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit
    )
    
    print("Executing historical trade simulation...")
    history_df, trades = backtester.run(df_signals)
    print(f"Simulation finished. Total trades executed: {len(trades)}")
    
    # 4. Calculate metrics
    metrics = calculate_performance_metrics(history_df, trades, args.capital)
    
    # 5. Display trades log
    if trades:
        print("\n--- TRADES LOG ---")
        trade_rows = []
        for i, t in enumerate(trades, 1):
            trade_rows.append([
                i,
                t['entry_date'],
                t['exit_date'],
                f"${t['entry_price']:,.2f}",
                f"${t['exit_price']:,.2f}",
                f"{t['size']:.6f} BTC",
                f"${t['profit']:+,.2f}",
                f"{t['return_pct']:+,.2f}%",
                f"${t['fee']:,.2f}",
                t.get('exit_reason', 'Signal')
            ])
        headers = ["#", "Entry Date", "Exit Date", "Entry Price", "Exit Price", "Size", "Profit", "Return %", "Total Fee", "Exit Reason"]
        print(tabulate(trade_rows, headers=headers, tablefmt="grid"))
    else:
        print("\n[!] No trades executed during this backtest window.")
        
    # 6. Display metrics summary
    print("\n--- PERFORMANCE SUMMARY ---")
    metrics_rows = [
        ["Initial Capital", f"${metrics['initial_value']:,.2f} USDT"],
        ["Final Portfolio Value", f"${metrics['final_value']:,.2f} USDT"],
        ["Total Return (%)", f"{metrics['total_return_pct']:+,.2f}%"],
        ["Annualized Return (%)", f"{metrics['annualized_return_pct']:+,.2f}%"],
        ["Buy & Hold Return (%)", f"{metrics['buy_and_hold_return_pct']:+,.2f}%"],
        ["Sharpe Ratio", f"{metrics['sharpe_ratio']:.4f}"],
        ["Maximum Drawdown (%)", f"{metrics['max_drawdown_pct']:.2f}%"],
        ["Total Trades Executed", metrics['total_trades']],
        ["Win Rate (%)", f"{metrics['win_rate_pct']:.2f}%"],
        ["Profit Factor", f"{metrics['profit_factor']:.4f}"]
    ]
    print(tabulate(metrics_rows, headers=["Performance Indicator", "Value"], tablefmt="fancy_grid"))
    
    # 7. Render terminal trend chart
    render_ascii_price_chart(df_signals, limit=20)
    
    # 8. Generate and save matplotlib chart
    plot_equity_curve(history_df, trades, args.plot)
    print("\n=======================================================")
    print("                BACKTEST RUN COMPLETED                 ")
    print("=======================================================\n")

if __name__ == '__main__':
    main()
