import os
import sys
import pandas as pd
import numpy as np
import itertools

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.loader import get_ohlcv
from strategies.breakout import AdaptiveHighBetaBreakoutStrategy

def run_optimization():
    symbols = ['SOL/USDT', 'DOGE/USDT', 'ADA/USDT', 'LINK/USDT', 'DOT/USDT']
    start_date = '2024-01-01'
    end_date = '2026-06-01'
    timeframe = '4h'
    
    donchian_windows = [10, 20, 30, 40]
    vol_thresholds = [0.8, 1.0, 1.2, 1.5]
    atr_stop_multipliers = [1.5, 2.0, 2.5, 3.0]
    atr_tp_multipliers = [4.0, 6.0, 8.0, 10.0]
    
    print("=====================================================")
    print(" HIGH-BETA VOLATILITY BREAKOUT OPTIMIZATION (256 RUNS)")
    print("=====================================================")
    
    raw_data = {}
    for sym in symbols:
        try:
            print(f"Loading {sym}...")
            df = get_ohlcv(sym, timeframe, start_date, end_date)
            if not df.empty:
                raw_data[sym] = df[~df.index.duplicated(keep='first')]
        except Exception as e:
            pass
            
    if not raw_data:
        print("No data available.")
        return
        
    base_dates = list(raw_data.values())[0].index
    results = []
    
    print("\nExecuting Optimization Grid...")
    
    for d_win in donchian_windows:
        for v_thresh in vol_thresholds:
            strategy = AdaptiveHighBetaBreakoutStrategy(params={
                'atr_window': 14,
                'baseline_window': 50,
                'donchian_window': d_win,
                'vol_threshold': v_thresh
            })
            
            sig_data = {}
            for sym, df in raw_data.items():
                sig_data[sym] = strategy.generate_signals(df)
                
            for stop_mult in atr_stop_multipliers:
                for tp_mult in atr_tp_multipliers:
                    
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
                    
                    for t in range(1, len(base_dates)):
                        current_time = base_dates[t]
                        current_total_equity = 0.0
                        
                        for sym in symbols:
                            if sym not in sig_data: continue
                            df = sig_data[sym]
                            if current_time not in df.index: continue
                            
                            idx = df.index.get_loc(current_time)
                            
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
                        if sym not in sig_data: continue
                        port = portfolio[sym]
                        last_close = sig_data[sym]['Close'].iloc[-1]
                        
                        coin_equity = port['free_cash']
                        if port['status'] == 'LONG':
                            proceeds = port['qty'] * last_close
                            fee = proceeds * fee_rate
                            coin_equity += proceeds - fee
                        final_equity += coin_equity

                    equity_series = pd.Series(equity_curve, index=dates_curve)
                    sharpe = 0
                    cagr = 0
                    max_drawdown = 0
                    net_return = (final_equity - initial_capital) / initial_capital
                    
                    if not equity_series.empty:
                        peak = equity_series.expanding(min_periods=1).max()
                        drawdown = (equity_series - peak) / peak
                        max_drawdown = drawdown.min()
                        
                        days = (dates_curve[-1] - dates_curve[0]).days
                        cagr = (final_equity / initial_capital) ** (365.25 / days) - 1 if days > 0 else 0
                        
                        daily_equity = equity_series.resample('1D').last().dropna()
                        returns = daily_equity.pct_change().dropna()
                        sharpe = (returns.mean() / returns.std()) * np.sqrt(365.25) if returns.std() != 0 else 0
                        
                    results.append({
                        'Donchian': d_win,
                        'VolThresh': v_thresh,
                        'StopMult': stop_mult,
                        'TPMult': tp_mult,
                        'NetReturn': net_return,
                        'MaxDrawdown': max_drawdown,
                        'Sharpe': sharpe
                    })
                    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by=['Sharpe', 'NetReturn', 'MaxDrawdown'], ascending=[False, False, True])
    
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'breakout_optimization_results.csv')
    results_df.to_csv(out_path, index=False)
    
    print("\nTop 10 Configurations:")
    print(results_df.head(10).to_string(index=False))

if __name__ == "__main__":
    run_optimization()
