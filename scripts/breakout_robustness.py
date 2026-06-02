import os
import sys
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.loader import get_ohlcv
from strategies.breakout import AdaptiveHighBetaBreakoutStrategy

def run_robustness():
    symbols = ['SOL/USDT', 'DOGE/USDT', 'ADA/USDT', 'LINK/USDT', 'DOT/USDT']
    
    timeframes = ['1h', '4h', '1d']
    regimes = [
        ('2022 Bear Market', '2022-01-01', '2022-12-31'),
        ('2023-2024 Bull Market', '2023-01-01', '2024-12-31'),
        ('2025-2026 Recent Cycle', '2025-01-01', '2026-06-01'),
        ('Full Period', '2022-01-01', '2026-06-01')
    ]
    
    # Optimized Params
    d_win = 20
    v_thresh = 1.2
    stop_mult = 2.0
    tp_mult = 10.0
    
    strategy = AdaptiveHighBetaBreakoutStrategy(params={
        'atr_window': 14,
        'baseline_window': 50,
        'donchian_window': d_win,
        'vol_threshold': v_thresh
    })
    
    results = []
    
    print("=====================================================")
    print(" HIGH-BETA VOLATILITY BREAKOUT ROBUSTNESS TEST")
    print("=====================================================")
    
    for tf in timeframes:
        print(f"\n--- Testing Timeframe: {tf} ---")
        
        # Load data for full period starting from 2021 to warm up indicators
        raw_data = {}
        for sym in symbols:
            try:
                df = get_ohlcv(sym, tf, '2021-01-01', '2026-06-01') 
                if not df.empty:
                    raw_data[sym] = df[~df.index.duplicated(keep='first')]
            except Exception as e:
                pass
                
        if not raw_data:
            continue
            
        # Precompute signals for full history
        sig_data = {}
        for sym, df in raw_data.items():
            sig_data[sym] = strategy.generate_signals(df)
            
        for regime_name, start_date, end_date in regimes:
            print(f"  -> Regime: {regime_name}")
            
            regime_sig_data = {}
            for sym, df in sig_data.items():
                mask = (df.index >= start_date) & (df.index <= end_date)
                regime_df = df.loc[mask]
                if not regime_df.empty:
                    regime_sig_data[sym] = regime_df
            
            if not regime_sig_data:
                continue
                
            # FIX: Create an unbroken timeline by unionizing all available indices
            all_dates = pd.DatetimeIndex([])
            for df in regime_sig_data.values():
                all_dates = all_dates.union(df.index)
            base_dates = all_dates.sort_values()
            
            if len(base_dates) == 0:
                continue
                
            initial_capital = 10000.0
            capital_per_coin = initial_capital / len(symbols)
            
            portfolio = {
                sym: {
                    'status': 'FLAT',
                    'free_cash': capital_per_coin,
                    'qty': 0.0,
                    'entry_price': 0.0,
                    'highest_close': 0.0,
                    'trailing_stop_price': 0.0,
                    'take_profit_price': 0.0
                } for sym in symbols
            }
            
            fee_rate = 0.001       
            slippage_rate = 0.0005 
            
            equity_curve = []
            dates_curve = []
            
            total_trades = 0
            winning_trades = 0
            
            for t in range(1, len(base_dates)):
                current_time = base_dates[t]
                current_total_equity = 0.0
                
                for sym in symbols:
                    if sym not in regime_sig_data: continue
                    df = regime_sig_data[sym]
                    if current_time not in df.index: continue
                    
                    idx = df.index.get_loc(current_time)
                    if idx == 0: continue
                    
                    prev_signal = df['Signal'].iloc[idx-1]
                    prev_atr = df['atr'].iloc[idx-1]
                    
                    curr_open = df['Open'].iloc[idx]
                    curr_high = df['High'].iloc[idx]
                    curr_low = df['Low'].iloc[idx]
                    curr_close = df['Close'].iloc[idx]
                    curr_atr = df['atr'].iloc[idx]
                    
                    port = portfolio[sym]
                    
                    if port['status'] == 'FLAT':
                        if prev_signal == 1.0 and not pd.isna(prev_atr):
                            exec_price = curr_open * (1 + slippage_rate)
                            notional = port['free_cash'] * 0.99 
                            qty = notional / exec_price
                            fee = notional * fee_rate
                            
                            port['free_cash'] -= notional + fee
                            port['qty'] = qty
                            port['entry_price'] = exec_price
                            port['highest_close'] = curr_close 
                            
                            initial_stop = exec_price - (stop_mult * prev_atr)
                            port['take_profit_price'] = exec_price + (tp_mult * prev_atr)
                            port['trailing_stop_price'] = initial_stop
                            
                            port['status'] = 'LONG'
                            
                    elif port['status'] == 'LONG':
                        exit_triggered = False
                        exit_price = 0.0
                        
                        if prev_signal == -1.0:
                            exit_triggered = True
                            exit_price = curr_open * (1 - slippage_rate)
                        elif curr_low <= port['trailing_stop_price']:
                            exit_triggered = True
                            actual_fill = min(curr_open, port['trailing_stop_price'])
                            exit_price = actual_fill * (1 - slippage_rate)
                        elif curr_high >= port['take_profit_price']:
                            exit_triggered = True
                            actual_fill = max(curr_open, port['take_profit_price'])
                            exit_price = actual_fill * (1 - slippage_rate)
                            
                        if exit_triggered:
                            proceeds = port['qty'] * exit_price
                            fee = proceeds * fee_rate
                            port['free_cash'] += proceeds - fee
                            
                            pnl = proceeds - fee - (port['qty'] * port['entry_price'])
                            if pnl > 0:
                                winning_trades += 1
                            total_trades += 1
                            
                            port['qty'] = 0.0
                            port['status'] = 'FLAT'
                        else:
                            port['highest_close'] = max(port['highest_close'], curr_close)
                            new_trailing_stop = port['highest_close'] - (stop_mult * curr_atr)
                            port['trailing_stop_price'] = max(port['trailing_stop_price'], new_trailing_stop)
                    
                    coin_equity = port['free_cash']
                    if port['status'] == 'LONG':
                        coin_equity += port['qty'] * curr_close
                    current_total_equity += coin_equity
                    
                equity_curve.append(current_total_equity)
                dates_curve.append(current_time)
                
            final_equity = 0.0
            for sym in symbols:
                if sym not in regime_sig_data: continue
                port = portfolio[sym]
                last_close = regime_sig_data[sym]['Close'].iloc[-1]
                
                coin_equity = port['free_cash']
                if port['status'] == 'LONG':
                    proceeds = port['qty'] * last_close
                    fee = proceeds * fee_rate
                    coin_equity += proceeds - fee
                final_equity += coin_equity

            equity_series = pd.Series(equity_curve, index=dates_curve)
            sharpe = 0
            max_drawdown = 0
            net_return = (final_equity - initial_capital) / initial_capital
            
            if not equity_series.empty:
                peak = equity_series.expanding(min_periods=1).max()
                drawdown = (equity_series - peak) / peak
                max_drawdown = drawdown.min()
                
                daily_equity = equity_series.resample('1D').last().dropna()
                if len(daily_equity) > 1:
                    returns = daily_equity.pct_change().dropna()
                    if returns.std() != 0:
                        sharpe = (returns.mean() / returns.std()) * np.sqrt(365.25)
                        
            win_rate = (winning_trades / total_trades) if total_trades > 0 else 0
            
            results.append({
                'Timeframe': tf,
                'Regime': regime_name,
                'Net Return': f"{net_return*100:.2f}%",
                'Max Drawdown': f"{max_drawdown*100:.2f}%",
                'Sharpe Ratio': f"{sharpe:.2f}",
                'Total Trades': total_trades,
                'Win Rate': f"{win_rate*100:.1f}%"
            })
            
    results_df = pd.DataFrame(results)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'breakout_robustness_results.csv')
    results_df.to_csv(out_path, index=False)
    
    print("\nRobustness Comparative Matrix:")
    print(results_df.to_string(index=False))

if __name__ == "__main__":
    run_robustness()
