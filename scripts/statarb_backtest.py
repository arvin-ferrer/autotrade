import os
import sys
import pandas as pd
import numpy as np
import argparse
from statsmodels.tsa.stattools import adfuller

# Adjust python path to be able to import from data.loader
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.loader import get_ohlcv

def run_pairs_simulation(start_date: str, end_date: str, timeframe: str = '1d'):
    print(f"Fetching data for BTC/USDT and ETH/USDT ({start_date} to {end_date})...")
    df_a = get_ohlcv('BTC/USDT', timeframe, start_date=start_date, end_date=end_date)
    df_b = get_ohlcv('ETH/USDT', timeframe, start_date=start_date, end_date=end_date)

    # Keep only Open and Close prices
    df_a = df_a[['Open', 'Close']].rename(columns={'Open': 'Open_A', 'Close': 'Close_A'})
    df_b = df_b[['Open', 'Close']].rename(columns={'Open': 'Open_B', 'Close': 'Close_B'})

    # Merge on index
    df = df_a.join(df_b, how='inner').dropna()

    if df.empty:
        print("Data is empty.")
        return

    # Log prices
    df['y'] = np.log(df['Close_A'])
    df['x'] = np.log(df['Close_B'])

    print("Running simulation loop with ADF Cointegration Gating and Percentile Bounds...")
    N = 60
    capital = 10000.0
    fee_rate = 0.001
    
    position = 0 # 0: None, 1: Long Spread, -1: Short Spread
    qty_A = 0.0
    qty_B = 0.0
    entry_price_A = 0.0
    entry_price_B = 0.0
    
    locked_beta = 0.0
    locked_alpha = 0.0
    locked_pct_50 = 0.0
    locked_pct_sl = 0.0
    
    pending_entry = 0
    pending_exit = False
    
    # For Buy and Hold benchmark
    bh_qty_A = 5000.0 / df['Close_A'].iloc[N]
    bh_qty_B = 5000.0 / df['Close_B'].iloc[N]
        
    for t in range(N, len(df)):
        # Process pending executions at OPEN of current bar (t)
        open_a = df['Open_A'].iloc[t]
        open_b = df['Open_B'].iloc[t]
        
        if pending_exit:
            if position == 1:
                pnl_a = qty_A * (open_a - entry_price_A)
                pnl_b = qty_B * (entry_price_B - open_b)
                close_value = (qty_A * open_a) + (qty_B * open_b)
                capital += pnl_a + pnl_b - (close_value * fee_rate)
                position = 0
                pending_exit = False
            elif position == -1:
                pnl_a = qty_A * (entry_price_A - open_a)
                pnl_b = qty_B * (open_b - entry_price_B)
                close_value = (qty_A * open_a) + (qty_B * open_b)
                capital += pnl_a + pnl_b - (close_value * fee_rate)
                position = 0
                pending_exit = False
                
        if pending_entry != 0:
            position = pending_entry
            # For a true hedge, beta should be factored into position sizing, but here we equalize USD capital 50/50
            qty_A = (capital / 2) / open_a
            qty_B = (capital / 2) / open_b
            entry_price_A = open_a
            entry_price_B = open_b
            capital -= (capital / 2) * fee_rate * 2
            pending_entry = 0

        # End of bar t (logic using Close prices)
        y_t = df['y'].iloc[t]
        x_t = df['x'].iloc[t]
        
        if position == 0:
            # Calculate OLS over window t-N+1 to t
            window_y = df['y'].iloc[t-N+1 : t+1].values
            window_x = df['x'].iloc[t-N+1 : t+1].values
            
            # OLS y = beta * x + alpha
            beta, alpha = np.polyfit(window_x, window_y, 1)
            error = window_y - (beta * window_x + alpha)
            
            error_t = error[-1]
            
            # Cointegration Gate
            try:
                adf_result = adfuller(error)
                p_value = adf_result[1]
            except Exception:
                p_value = 1.0 # Failed ADF, gate closed
            
            if p_value < 0.05:
                pct_99, pct_95, pct_50, pct_5, pct_1 = np.percentile(error, [99, 95, 50, 5, 1])
                
                if error_t <= pct_5:
                    pending_entry = 1
                    locked_beta = beta
                    locked_alpha = alpha
                    locked_pct_50 = pct_50
                    locked_pct_sl = pct_1
                elif error_t >= pct_95:
                    pending_entry = -1
                    locked_beta = beta
                    locked_alpha = alpha
                    locked_pct_50 = pct_50
                    locked_pct_sl = pct_99

        elif position == 1:
            realized_error = y_t - (locked_beta * x_t + locked_alpha)
            if realized_error >= locked_pct_50 or realized_error <= locked_pct_sl:
                pending_exit = True
                
        elif position == -1:
            realized_error = y_t - (locked_beta * x_t + locked_alpha)
            if realized_error <= locked_pct_50 or realized_error >= locked_pct_sl:
                pending_exit = True

    # Force close at end of dataset using last close price
    if position == 1:
        close_a = df['Close_A'].iloc[-1]
        close_b = df['Close_B'].iloc[-1]
        pnl_a = qty_A * (close_a - entry_price_A)
        pnl_b = qty_B * (entry_price_B - close_b)
        close_value = (qty_A * close_a) + (qty_B * close_b)
        capital += pnl_a + pnl_b - close_value * fee_rate
    elif position == -1:
        close_a = df['Close_A'].iloc[-1]
        close_b = df['Close_B'].iloc[-1]
        pnl_a = qty_A * (entry_price_A - close_a)
        pnl_b = qty_B * (close_b - entry_price_B)
        close_value = (qty_A * close_a) + (qty_B * close_b)
        capital += pnl_a + pnl_b - close_value * fee_rate

    final_bh = bh_qty_A * df['Close_A'].iloc[-1] + bh_qty_B * df['Close_B'].iloc[-1]
    
    print(f"\n=====================================================")
    print(f" STATISTICAL ARBITRAGE (PAIRS TRADING) ENGINE")
    print(f" Period: {start_date} to {end_date}")
    print(f"=====================================================")
    print(f" Initial Capital: $10000.00")
    print(f" Final Equity:    ${capital:.2f}")
    print(f" Net Return:      {((capital - 10000) / 10000) * 100:.2f}%")
    print(f" ----------------------------------------------------")
    print(f" Buy & Hold (50/50 BTC/ETH): ${final_bh:.2f}")
    print(f" Buy & Hold Return: {((final_bh - 10000) / 10000) * 100:.2f}%")
    print(f"=====================================================\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=str, default='2021-01-01')
    parser.add_argument('--end', type=str, default='2024-05-01')
    args = parser.parse_args()
    
    run_pairs_simulation(args.start, args.end)
