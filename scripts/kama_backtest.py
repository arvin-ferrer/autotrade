import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.loader import get_ohlcv

import argparse

def run_kama_backtest():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeframe', type=str, default='1d')
    parser.add_argument('--start', type=str, default='2021-01-01')
    parser.add_argument('--end', type=str, default='2024-05-01')
    args = parser.parse_args()
    
    timeframe = args.timeframe
    start_date = args.start
    end_date = args.end

    symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
        'ADA/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT',
        'AVAX/USDT', 'LTC/USDT', 'ATOM/USDT', 'UNI/USDT', 'BCH/USDT'
    ]
    
    print("=====================================================")
    print(f" KAMA + MACRO GATE BACKTEST ENGINE ({timeframe})")
    print(f" Period: {start_date} to {end_date}")
    print("=====================================================")
    
    data = {}
    for sym in symbols:
        try:
            df = get_ohlcv(sym, timeframe, start_date, end_date)
            if not df.empty: data[sym] = df
        except Exception: pass
            
    print("Calculating KAMA Indicators...")
    
    indicators = {}
    for sym, df in data.items():
        close = df['Close']
        
        # KAMA Parameters
        n = 10
        fast_ema_n = 2
        slow_ema_n = 30
        
        fastest_sc = 2 / (fast_ema_n + 1)
        slowest_sc = 2 / (slow_ema_n + 1)
        
        change = close.diff(n).abs()
        volatility = close.diff(1).abs().rolling(n).sum()
        
        er = change / volatility
        sc = (er * (fastest_sc - slowest_sc) + slowest_sc) ** 2
        
        # Calculate KAMA
        kama = np.zeros_like(close)
        kama[:] = np.nan
        
        close_arr = close.values
        sc_arr = sc.values
        
        # Find first valid index
        first_valid = sc.first_valid_index()
        if first_valid is not None:
            idx = close.index.get_loc(first_valid)
            kama[idx-1] = close_arr[idx-1] # Initialize KAMA with previous close
            
            for i in range(idx, len(close_arr)):
                kama[i] = kama[i-1] + sc_arr[i] * (close_arr[i] - kama[i-1])
                
        kama_series = pd.Series(kama, index=close.index)
        
        indicators[sym] = pd.DataFrame({
            'close': close,
            'kama': kama_series,
            'er': er,
            'next_open': df['Open'].shift(-1)
        })
        
    print("Executing backtest...")
    
    dates = data['BTC/USDT'].index
    
    # 3. FIX: Move Macro Gate calculation OUTSIDE the daily loop (O(N) instead of O(N^2))
    btc_close = data['BTC/USDT']['Close']
    btc_sma100 = btc_close.rolling(100).mean()
    gate_open = pd.Series(index=btc_close.index, dtype=bool)
    current_gate = False
    for j in range(len(btc_close)):
        c_val = btc_close.iloc[j]
        s_val = btc_sma100.iloc[j]
        if pd.isna(s_val):
            gate_open.iloc[j] = False
            continue
        if not current_gate and c_val > s_val * 1.02: current_gate = True
        elif current_gate and c_val < s_val * 0.98: current_gate = False
        gate_open.iloc[j] = current_gate
    
    initial_capital = 10000.0
    capital = initial_capital
    holdings = {sym: 0.0 for sym in symbols}
    entry_prices = {sym: 0.0 for sym in symbols}
    
    fee_rate = 0.001
    equity_curve = []
    
    for i in range(50, len(dates) - 1):
        current_date = dates[i]
        prev_date = dates[i-1]
        
        is_macro_open = gate_open.loc[prev_date] if prev_date in gate_open.index else False
        
        # Step 1: Liquidations
        for sym in symbols:
            if holdings[sym] > 0.0:
                ind = indicators[sym]
                
                # 1. FIX: Use .loc[prev_date] instead of .iloc[i-1] to prevent unaligned index data leaks
                if prev_date not in ind.index: continue
                
                prev_close = ind.loc[prev_date, 'close']
                prev_kama = ind.loc[prev_date, 'kama']
                
                # Exit if close crosses below KAMA, OR if Macro Gate closes
                exit_signal = (prev_close < prev_kama) or (not is_macro_open)
                
                if exit_signal:
                    exec_price = ind.loc[prev_date, 'next_open']
                    if pd.isna(exec_price): continue
                    
                    sell_val = holdings[sym] * exec_price
                    fee = sell_val * fee_rate
                    capital += (sell_val - fee)
                    
                    holdings[sym] = 0.0
                    entry_prices[sym] = 0.0
                    
        # Mark to market for position sizing
        current_equity = capital
        for sym in symbols:
            if holdings[sym] > 0.0:
                # Use current_date for equity calculation
                if current_date in indicators[sym].index:
                    current_equity += holdings[sym] * indicators[sym].loc[current_date, 'close']
                    
        # Step 2: Entries
        buy_candidates = []
        if is_macro_open:
            for sym in symbols:
                if holdings[sym] == 0.0:
                    ind = indicators[sym]
                    if prev_date not in ind.index: continue
                    
                    prev_close = ind.loc[prev_date, 'close']
                    prev_kama = ind.loc[prev_date, 'kama']
                    prev_er = ind.loc[prev_date, 'er']
                    
                    # Entry: Close > KAMA and ER > 0.30 (Trending)
                    if prev_close > prev_kama and prev_er > 0.30:
                        buy_candidates.append(sym)
                    
        max_positions = 5
        current_positions = sum(1 for sym in symbols if holdings[sym] > 0)
        available_slots = max_positions - current_positions
        
        if buy_candidates and available_slots > 0:
            # Sort by Efficiency Ratio (smoothest trends first)
            buy_candidates.sort(key=lambda s: indicators[s].loc[prev_date, 'er'], reverse=True)
            to_buy = buy_candidates[:available_slots]
            
            # 2. FIX: Position Sizing Bug (Never YOLO > 20% equity into one asset)
            target_allocation = current_equity / max_positions
            allocation_per_asset = min(capital, target_allocation) * 0.99
                
            for sym in to_buy:
                exec_price = indicators[sym].loc[prev_date, 'next_open']
                if pd.isna(exec_price): continue
                
                buy_size = (allocation_per_asset * (1 - fee_rate)) / exec_price
                holdings[sym] = buy_size
                entry_prices[sym] = exec_price
                capital -= allocation_per_asset
                
        equity_curve.append(current_equity)

    equity_series = pd.Series(equity_curve)
    peak = equity_series.expanding(min_periods=1).max()
    drawdown = (equity_series - peak) / peak
    max_drawdown = drawdown.min()
    
    final_equity = equity_series.iloc[-1] if not equity_series.empty else initial_capital
    net_return = (final_equity - initial_capital) / initial_capital
    days = len(equity_curve)
    cagr = (final_equity / initial_capital) ** (365.25 / days) - 1 if days > 0 else 0
    
    returns = equity_series.pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * np.sqrt(365.25) if returns.std() != 0 else 0
    
    print("\n=====================================================")
    print("      KAMA FINAL PERFORMANCE TEAR SHEET")
    print("=====================================================")
    print(f"Test Period:      {dates[50].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")
    print(f"Initial Capital:  ${initial_capital:,.2f}")
    print(f"Final Equity:     ${final_equity:,.2f}")
    print("-----------------------------------------------------")
    print(f"Net Return:       {net_return*100:.2f}%")
    print(f"CAGR:             {cagr*100:.2f}%")
    print(f"Max Drawdown:     {max_drawdown*100:.2f}%")
    print(f"Sharpe Ratio:     {sharpe:.2f}")
    print("=====================================================\n")

if __name__ == "__main__":
    run_kama_backtest()
