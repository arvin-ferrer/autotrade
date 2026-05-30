import pandas as pd
import numpy as np
import os
import sys

# Ensure data package is accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.loader import get_ohlcv

def run_dip_buyer_backtest():
    symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
        'ADA/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT',
        'AVAX/USDT', 'LTC/USDT', 'ATOM/USDT', 'UNI/USDT', 'BCH/USDT'
    ]
    start_date = '2021-01-01'
    end_date = '2024-05-01'
    
    print("=====================================================")
    print(" FAST REGIME-FILTERED MEAN REVERSION (DIP BUYER)")
    print(f" Period: {start_date} to {end_date}")
    print("=====================================================")
    
    data = {}
    for sym in symbols:
        try:
            df = get_ohlcv(sym, '1d', start_date, end_date)
            if not df.empty: data[sym] = df
        except Exception: pass
            
    if 'BTC/USDT' not in data:
        print("Error: BTC data missing. Cannot calculate Macro Gate.")
        return
        
    print("Calculating Technical Indicators...")
    
    # 1. Macro Gate (BTC EMA-21)
    btc_df = data['BTC/USDT']
    btc_close = btc_df['Close']
    btc_ema21 = btc_close.ewm(span=21, adjust=False).mean()
    gate_open = btc_close > btc_ema21
    
    # Pre-calculate RSI_3 and SMA_50 for all assets
    indicators = {}
    for sym, df in data.items():
        close = df['Close']
        
        # SMA 50
        sma50 = close.rolling(50).mean()
        
        # RSI 3
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=3).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=3).mean()
        rs = gain / loss
        rsi3 = 100 - (100 / (1 + rs))
        
        # We also need next day open to execute trades realistically
        next_open = df['Open'].shift(-1)
        
        # ATR 14
        high = df['High']
        low = df['Low']
        high_low = high - low
        high_cp = (high - close.shift()).abs()
        low_cp = (low - close.shift()).abs()
        tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
        atr14 = tr.ewm(alpha=1/14, adjust=False).mean()
        
        indicators[sym] = {
            'close': close,
            'sma50': sma50,
            'rsi3': rsi3,
            'atr14': atr14,
            'next_open': next_open
        }
        
    print("Executing backtest...")
    
    # Align dates
    dates = btc_df.index
    
    initial_capital = 10000.0
    capital = initial_capital
    holdings = {sym: 0.0 for sym in symbols}
    entry_prices = {sym: 0.0 for sym in symbols}
    holding_days = {sym: 0 for sym in symbols}
    entry_atrs = {sym: 0.0 for sym in symbols}
    
    fee_rate = 0.001
    
    equity_curve = []
    trade_log = []
    
    # State tracking
    wins = 0
    losses = 0
    
    for i in range(50, len(dates) - 1): # Start at 50 for SMA50 warmup
        current_date = dates[i]
        
        # Look-ahead bias shield: Evaluate yesterday's signals to execute today
        prev_date = dates[i-1]
        
        # Step 1: Liquidations & Exits
        for sym in symbols:
            if holdings[sym] > 0.0:
                holding_days[sym] += 1
                ind = indicators[sym]
                
                # Exit triggers based on yesterday's close
                prev_close = ind['close'].iloc[i-1]
                prev_rsi3 = ind['rsi3'].iloc[i-1]
                
                take_profit = prev_rsi3 > 70
                stop_loss = prev_close < (entry_prices[sym] - 2.0 * entry_atrs[sym])
                time_stop = holding_days[sym] >= 7
                
                if take_profit or stop_loss or time_stop:
                    # Execute at today's open
                    exec_price = ind['next_open'].iloc[i-1] # which is today's open
                    sell_val = holdings[sym] * exec_price
                    fee = sell_val * fee_rate
                    capital += (sell_val - fee)
                    
                    profit_pct = (exec_price / entry_prices[sym]) - 1.0 - (fee_rate * 2)
                    if profit_pct > 0: wins += 1
                    else: losses += 1
                    
                    holdings[sym] = 0.0
                    entry_prices[sym] = 0.0
                    holding_days[sym] = 0
                    entry_atrs[sym] = 0.0
                    
        # Step 2: Entries
        # Only enter if Macro Gate was open yesterday
        is_macro_open = gate_open.iloc[i-1]
        
        if is_macro_open:
            buy_candidates = []
            for sym in symbols:
                if holdings[sym] == 0.0:
                    ind = indicators[sym]
                    prev_close = ind['close'].iloc[i-1]
                    prev_sma50 = ind['sma50'].iloc[i-1]
                    prev_rsi3 = ind['rsi3'].iloc[i-1]
                    
                    if prev_rsi3 < 15 and prev_close > prev_sma50:
                        buy_candidates.append(sym)
                        
            # If multiple candidates, we split capital evenly among them (max 5 positions)
            max_positions = 5
            current_positions = sum(1 for sym in symbols if holdings[sym] > 0)
            available_slots = max_positions - current_positions
            
            if buy_candidates and available_slots > 0:
                # Sort by RSI3 (lowest RSI3 gets priority)
                buy_candidates.sort(key=lambda s: indicators[s]['rsi3'].iloc[i-1])
                to_buy = buy_candidates[:available_slots]
                
                # Split available capital
                allocation_per_asset = (capital * 0.99) / max(1, len(to_buy)) # Use 99% of available cash
                if allocation_per_asset > capital:
                    allocation_per_asset = capital
                    
                for sym in to_buy:
                    exec_price = indicators[sym]['next_open'].iloc[i-1]
                    if pd.isna(exec_price): continue
                    
                    buy_size = (allocation_per_asset * (1 - fee_rate)) / exec_price
                    holdings[sym] = buy_size
                    entry_prices[sym] = exec_price
                    holding_days[sym] = 1
                    entry_atrs[sym] = indicators[sym]['atr14'].iloc[i-1]
                    capital -= allocation_per_asset
                    
        # Mark to market daily equity
        current_equity = capital
        for sym in symbols:
            if holdings[sym] > 0.0:
                current_equity += holdings[sym] * indicators[sym]['close'].iloc[i]
        equity_curve.append(current_equity)

    # Calculate Performance Metrics
    equity_series = pd.Series(equity_curve)
    peak = equity_series.expanding(min_periods=1).max()
    drawdown = (equity_series - peak) / peak
    max_drawdown = drawdown.min()
    
    net_return = (capital - initial_capital) / initial_capital
    days = len(equity_curve)
    cagr = (capital / initial_capital) ** (365.25 / days) - 1 if days > 0 else 0
    
    returns = equity_series.pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * np.sqrt(365.25) if returns.std() != 0 else 0
    
    print("\n=====================================================")
    print("      DIP BUYER FINAL PERFORMANCE TEAR SHEET")
    print("=====================================================")
    print(f"Test Period:      {dates[50].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")
    print(f"Initial Capital:  ${initial_capital:,.2f}")
    print(f"Final Equity:     ${capital:,.2f}")
    print("-----------------------------------------------------")
    print(f"Net Return:       {net_return*100:.2f}%")
    print(f"CAGR:             {cagr*100:.2f}%")
    print(f"Max Drawdown:     {max_drawdown*100:.2f}%")
    print(f"Sharpe Ratio:     {sharpe:.2f}")
    print(f"Win Rate:         {(wins/(wins+losses)*100) if wins+losses > 0 else 0:.1f}% ({wins}W / {losses}L)")
    print("=====================================================\n")

if __name__ == "__main__":
    run_dip_buyer_backtest()
