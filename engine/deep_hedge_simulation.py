import pandas as pd
import numpy as np
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.loader import get_ohlcv
from strategies.simple import VolumeRSIStrategy

def run_deep_simulation():
    print("=== DEEP SIMULATION: DELTA-NEUTRAL HEDGING ===")
    
    # Configuration
    symbol = 'BTC/USDT'
    timeframe = '1h'
    start_date = '2025-11-01'
    end_date = '2026-05-25'
    initial_capital = 10000.0
    fee_rate = 0.001
    
    # Asymmetric Risk Parameters
    stop_loss_pct = 0.01   # 1%
    take_profit_pct = 0.10 # 10%
    
    print(f"Loading data for {symbol} {timeframe}...")
    df = get_ohlcv(symbol, timeframe, start_date, end_date)
    
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
    trades = []
    equity_curve = []
    
    print("Running simulation with 1% SL and 10% TP...")
    for index, row in df_signals.iterrows():
        close_price = row['Close']
        signal = row.get('Signal', 0.0)
        
        # Risk Management (SL / TP) when LONG
        if position == 1:
            sl_price = entry_price * (1.0 - stop_loss_pct)
            tp_price = entry_price * (1.0 + take_profit_pct)
            
            risk_exit = False
            exit_reason = ""
            
            if close_price <= sl_price:
                risk_exit = True
                exit_reason = "Stop Loss"
                exit_price = sl_price
            elif close_price >= tp_price:
                risk_exit = True
                exit_reason = "Take Profit"
                exit_price = tp_price
                
            if risk_exit:
                # Execute exit (We enter Hedge state)
                profit = (exit_price - entry_price) / entry_price
                cash = cash * (1 + profit) * (1 - fee_rate)
                position = -1 # Enter Short Hedge
                trades.append({
                    'exit_time': str(index),
                    'type': exit_reason,
                    'price': exit_price,
                    'profit_pct': profit * 100,
                    'balance': cash
                })
        
        # Strategy Signals
        if signal == 1.0 and position != 1:
            # Enter Long
            if position == -1:
                # Close short hedge (assume small fee)
                cash = cash * (1 - fee_rate)
            position = 1
            entry_price = close_price * (1 + fee_rate)
            trades.append({
                'exit_time': str(index),
                'type': 'Enter Long (Unhedge)',
                'price': entry_price,
                'profit_pct': 0,
                'balance': cash
            })
            
        elif signal == -1.0 and position == 1:
            # Exit Long to Hedge
            profit = (close_price - entry_price) / entry_price
            cash = cash * (1 + profit) * (1 - fee_rate)
            position = -1 # Enter Short Hedge
            trades.append({
                'exit_time': str(index),
                'type': 'Exit Long (Hedge)',
                'price': close_price,
                'profit_pct': profit * 100,
                'balance': cash
            })
            
        # If in short hedge, we gain inverse return of the market (simplified)
        if position == -1:
            # Calculate 1h inverse return
            prev_close = df_signals.loc[:index].iloc[-2]['Close'] if len(df_signals.loc[:index]) > 1 else close_price
            inv_return = (prev_close - close_price) / prev_close
            # In a real perp, you gain when price drops
            cash = cash * (1 + inv_return)
            
        # Daily Equity Tracking
        equity_curve.append({
            'timestamp': str(index),
            'equity': cash
        })

    print(f"\nFinal Equity: ${cash:,.2f} ({(cash/initial_capital - 1)*100:+.2f}%)")
    
    # Save Data
    out_dir = '/home/arvin/.gemini/antigravity-cli/brain/710a01c6-3768-4d00-9326-5656617e7dc3'
    trades_file = os.path.join(out_dir, 'hedge_trades.json')
    equity_file = os.path.join(out_dir, 'hedge_equity.json')
    
    with open(trades_file, 'w') as f:
        json.dump(trades, f, indent=2)
    with open(equity_file, 'w') as f:
        json.dump(equity_curve, f, indent=2)
        
    print(f"Data saved to {trades_file} and {equity_file}")

if __name__ == "__main__":
    run_deep_simulation()
