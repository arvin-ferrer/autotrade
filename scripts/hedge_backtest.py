import os
import sys
import pandas as pd
import numpy as np
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.loader import get_ohlcv
from strategies.simple import VolumeRSIStrategy

def run_hedge_backtest():
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
    start_date = '2022-01-01'
    end_date = '2024-05-01'
    timeframe = '1h'
    
    print("=====================================================")
    print(" DELTA-NEUTRAL HEDGED VOLUMERSI BREAKOUT")
    print(f" Period: {start_date} to {end_date} | Timeframe: {timeframe}")
    print("=====================================================")
    
    data = {}
    strategy = VolumeRSIStrategy()
    
    for sym in symbols:
        try:
            print(f"Loading {sym}...")
            df = get_ohlcv(sym, timeframe, start_date, end_date)
            if not df.empty:
                df = strategy.generate_signals(df)
                data[sym] = df
        except Exception as e:
            print(f"Failed to load {sym}: {e}")
            
    if 'BTC/USDT' not in data:
        print("Missing BTC data.")
        return
        
    base_dates = data['BTC/USDT'].index
    print("Executing simulation...")
    
    initial_capital = 30000.0
    capital_per_coin = initial_capital / len(symbols)
    
    portfolio = {
        sym: {
            'free_cash': capital_per_coin,
            'spot_size': 0.0,
            'short_perp_size': 0.0,
            'long_entry_price': 0.0,
            'perp_entry_price': 0.0
        } for sym in symbols
    }
    
    fee_spot = 0.001
    fee_perp = 0.0005
    funding_rate = 0.0001
    
    equity_curve = []
    dates_curve = []
    start_idx = 21
    
    last_val = {sym: capital_per_coin for sym in symbols}
    
    for t in range(start_idx, len(base_dates)):
        current_time = base_dates[t]
        current_equity = 0.0
        
        for sym in symbols:
            if sym not in data: continue
            df = data[sym]
            if current_time not in df.index:
                current_equity += last_val[sym]
                continue
            
            idx = df.index.get_loc(current_time)
            if idx == 0:
                current_equity += last_val[sym]
                continue
            
            prev_low = df['Low'].iloc[idx-1]
            prev_high = df['High'].iloc[idx-1]
            prev_open_candle = df['Open'].iloc[idx-1]
            prev_signal = df['Signal'].iloc[idx-1]
            prev_atr = df['atr'].iloc[idx-1]
            curr_open = df['Open'].iloc[idx]
            
            port = portfolio[sym]
            
            # 1. Funding
            if current_time.hour % 8 == 0 and port['short_perp_size'] > 0:
                port['free_cash'] += port['short_perp_size'] * curr_open * funding_rate
            
            # 2. Process SL / TP
            if port['spot_size'] > 0 and port['short_perp_size'] == 0:
                if not pd.isna(prev_atr) and prev_atr > 0:
                    sl_price = port['long_entry_price'] - prev_atr
                    tp_price = port['long_entry_price'] + (prev_atr * 3)
                else:
                    sl_price = port['long_entry_price'] * 0.99
                    tp_price = port['long_entry_price'] * 1.10
                
                hit_sl = prev_low <= sl_price
                hit_tp = prev_high >= tp_price
                
                if hit_sl or hit_tp:
                    execute_price = min(sl_price, prev_open_candle) if hit_sl else max(tp_price, prev_open_candle)
                    port['short_perp_size'] = port['spot_size']
                    port['perp_entry_price'] = execute_price
                    port['free_cash'] -= port['short_perp_size'] * execute_price * fee_perp
                    port['long_entry_price'] = 0.0
                    
            # 3. Process Signals
            if port['spot_size'] > 0 and port['short_perp_size'] == 0:
                if prev_signal == -1.0:
                    port['short_perp_size'] = port['spot_size']
                    port['perp_entry_price'] = curr_open
                    port['free_cash'] -= port['short_perp_size'] * curr_open * fee_perp
                    port['long_entry_price'] = 0.0
                    
            elif port['spot_size'] > 0 and port['short_perp_size'] > 0:
                if prev_signal == 1.0:
                    pnl = (port['perp_entry_price'] - curr_open) * port['short_perp_size']
                    port['free_cash'] += pnl
                    port['free_cash'] -= port['short_perp_size'] * curr_open * fee_perp
                    port['short_perp_size'] = 0.0
                    port['perp_entry_price'] = 0.0
                    
                    if not pd.isna(prev_atr) and prev_atr > 0:
                        total_equity = port['free_cash'] + port['spot_size'] * curr_open
                        target_size = min((total_equity * 0.01) / prev_atr, total_equity * 0.99 / curr_open)
                        
                        if target_size > port['spot_size']:
                            buy_amt = target_size - port['spot_size']
                            cost = buy_amt * curr_open
                            if cost > port['free_cash']:
                                buy_amt = port['free_cash'] * 0.99 / curr_open
                                cost = buy_amt * curr_open
                            port['free_cash'] -= cost + (cost * fee_spot)
                            port['spot_size'] += buy_amt
                        elif target_size < port['spot_size']:
                            sell_amt = port['spot_size'] - target_size
                            proceeds = sell_amt * curr_open
                            port['free_cash'] += proceeds - (proceeds * fee_spot)
                            port['spot_size'] = target_size
                            
                    port['long_entry_price'] = curr_open
                    
            elif port['spot_size'] == 0:
                if prev_signal == 1.0:
                    if not pd.isna(prev_atr) and prev_atr > 0:
                        target_size = min((port['free_cash'] * 0.01) / prev_atr, port['free_cash'] * 0.99 / curr_open)
                        cost = target_size * curr_open
                        port['free_cash'] -= cost + (cost * fee_spot)
                        port['spot_size'] = target_size
                        port['long_entry_price'] = curr_open
            
            # 4. Mark to Market
            val = port['free_cash'] + (port['spot_size'] * curr_open)
            if port['short_perp_size'] > 0:
                val += port['short_perp_size'] * (port['perp_entry_price'] - curr_open)
            last_val[sym] = val
            current_equity += val
            
        equity_curve.append(current_equity)
        dates_curve.append(current_time)
        
    final_equity = 0.0
    for sym in symbols:
        if sym not in data: continue
        port = portfolio[sym]
        last_close = data[sym]['Close'].iloc[-1]
        
        val = port['free_cash'] + (port['spot_size'] * last_close)
        if port['short_perp_size'] > 0:
            val += port['short_perp_size'] * (port['perp_entry_price'] - last_close)
            val -= port['short_perp_size'] * last_close * fee_perp
            
        val -= port['spot_size'] * last_close * fee_spot
        final_equity += val
        
    equity_series = pd.Series(equity_curve, index=dates_curve)
    if not equity_series.empty:
        peak = equity_series.expanding(min_periods=1).max()
        drawdown = (equity_series - peak) / peak
        max_drawdown = drawdown.min()
        net_return = (final_equity - initial_capital) / initial_capital
        days = (dates_curve[-1] - dates_curve[0]).days
        cagr = (final_equity / initial_capital) ** (365.25 / days) - 1 if days > 0 else 0
        
        daily_equity = equity_series.resample('1D').last().dropna()
        returns = daily_equity.pct_change().dropna()
        sharpe = (returns.mean() / returns.std()) * np.sqrt(365.25) if returns.std() != 0 else 0
        
        print(f"\n=====================================================")
        print(f"      HEDGED STRATEGY FINAL PERFORMANCE TEAR SHEET")
        print(f"=====================================================")
        print(f"Initial Capital:  ${initial_capital:,.2f}")
        print(f"Final Equity:     ${final_equity:,.2f}")
        print(f"Net Return:       {net_return*100:.2f}%")
        print(f"CAGR:             {cagr*100:.2f}%")
        print(f"Max Drawdown:     {max_drawdown*100:.2f}%")
        print(f"Sharpe Ratio:     {sharpe:.2f}")
        print(f"=====================================================\n")

if __name__ == "__main__":
    run_hedge_backtest()
