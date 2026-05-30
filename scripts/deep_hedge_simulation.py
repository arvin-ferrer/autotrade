import pandas as pd
import numpy as np
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.loader import get_ohlcv
from strategies.simple import VolumeRSIStrategy

def run_deep_simulation():
    print("=========================================================")
    print("=== MULTI-CONDITION DEEP HEDGE SIMULATION ===")
    print("=========================================================\n")
    
    symbol = 'BTC/USDT'
    initial_capital = 10000.0
    fee_rate = 0.001
    
    # Passing dynamic stop-loss (mimicking our new fixed execution logic)
    stop_loss_pct = 0.02
    take_profit_pct = 0.05
    
    # 3 distinct 3-month market environments
    conditions = [
        {"name": "Bull Market  (Early 2023)", "start": "2023-01-01", "end": "2023-04-01"},
        {"name": "Bear Market  (Mid 2022)  ", "start": "2022-04-01", "end": "2022-07-01"},
        {"name": "Chop/Sideways (Mid 2023) ", "start": "2023-05-01", "end": "2023-08-01"}
    ]
    
    timeframes = ['15m', '1h', '4h', '1d']
    
    results = []
    
    for cond in conditions:
        print(f"--- Testing Environment: {cond['name']} ---")
        for tf in timeframes:
            try:
                df = get_ohlcv(symbol, tf, cond['start'], cond['end'])
            except Exception as e:
                print(f"  [!] Failed to fetch {tf}: {e}")
                continue
                
            if df.empty:
                print(f"  [!] No data for {tf}")
                continue
                
            params = {
                'rsi_window': 14,
                'oversold': 35,
                'overbought': 70,
                'vol_ma_window': 20,
                'vol_multiplier': 2.0
            }
            strategy = VolumeRSIStrategy(name="VolumeRSI_Hedge", params=params)
            df_signals = strategy.generate_signals(df)
            
            cash = initial_capital
            position = 0 # 0 = Flat/Hedged, 1 = Long Spot
            entry_price = 0.0
            
            for index, row in df_signals.iterrows():
                close_price = row['Close']
                signal = row.get('Signal', 0.0)
                
                # Risk Management
                if position == 1:
                    sl_price = entry_price * (1.0 - stop_loss_pct)
                    tp_price = entry_price * (1.0 + take_profit_pct)
                    
                    if close_price <= sl_price:
                        # Slippage simulated correctly (exit at sl_price or current close if gap)
                        fill_price = min(sl_price, close_price)
                        profit = (fill_price - entry_price) / entry_price
                        cash = cash * (1 + profit) * (1 - fee_rate)
                        position = -1
                    elif close_price >= tp_price:
                        # Take Profit
                        fill_price = max(tp_price, close_price)
                        profit = (fill_price - entry_price) / entry_price
                        cash = cash * (1 + profit) * (1 - fee_rate)
                        position = -1
                
                # Signals
                if signal == 1.0 and position != 1:
                    if position == -1:
                        cash = cash * (1 - fee_rate)
                    position = 1
                    entry_price = close_price * (1 + fee_rate)
                elif signal == -1.0 and position == 1:
                    profit = (close_price - entry_price) / entry_price
                    cash = cash * (1 + profit) * (1 - fee_rate)
                    position = -1
                    
                # Short Hedge PnL tracking
                if position == -1:
                    prev_close = df_signals.loc[:index].iloc[-2]['Close'] if len(df_signals.loc[:index]) > 1 else close_price
                    inv_return = (prev_close - close_price) / prev_close
                    cash = cash * (1 + inv_return)
            
            pnl_pct = (cash / initial_capital - 1) * 100
            print(f"  > {tf:<3} | Candles: {len(df):<5} | Final Equity: ${cash:,.2f} ({pnl_pct:+.2f}%)")
            results.append({
                'Market Condition': cond['name'].strip(),
                'TF': tf,
                'Final Equity': f"${cash:,.2f}",
                'PnL %': f"{pnl_pct:+.2f}%"
            })
        print()

    print("=========================================================")
    print("=== COMPREHENSIVE PERFORMANCE MATRIX ===")
    print("=========================================================")
    df_results = pd.DataFrame(results)
    print(df_results.to_string(index=False))

if __name__ == "__main__":
    run_deep_simulation()
