import os
import sys
import pandas as pd
import numpy as np
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.loader import get_ohlcv

def simulate_funding_rates(df: pd.DataFrame, timeframe_hours: int = 8) -> pd.Series:
    """
    Simulates annualized funding rates (APR) based on price momentum.
    In real crypto markets, funding rates spike when speculators aggressively long the market.
    """
    # 10-day momentum (assuming 8h candles -> 30 periods)
    periods_10d = int((24 / timeframe_hours) * 10)
    if len(df) < periods_10d + 1:
        return pd.Series(0.10, index=df.index)
        
    momentum = df['Close'].pct_change(periods_10d)
    
    # Base APR is 10.95% (standard 0.01% per 8h). We add scaled momentum.
    simulated_apr = 0.1095 + (momentum * 2.0)
    
    # Cap APR between -20% and +150% for realism
    simulated_apr = simulated_apr.clip(lower=-0.20, upper=1.50)
    
    # Forward fill NaNs for the initial window
    simulated_apr = simulated_apr.fillna(0.1095)
    
    return simulated_apr

def run_funding_arb_backtest():
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'AVAX/USDT']
    start_date = '2023-01-01'
    end_date = '2024-05-01'
    timeframe = '8h'
    
    print("=====================================================")
    print(" STRUCTURAL BASIS & FUNDING ARBITRAGE (CASH & CARRY)")
    print(f" Period: {start_date} to {end_date} | Timeframe: {timeframe}")
    print("=====================================================")
    
    data = {}
    for sym in symbols:
        try:
            print(f"Loading {sym}...")
            df = get_ohlcv(sym, timeframe, start_date, end_date)
            if not df.empty:
                # Deduplicate index if needed
                df = df[~df.index.duplicated(keep='first')]
                df['simulated_apr'] = simulate_funding_rates(df, timeframe_hours=8)
                data[sym] = df
        except Exception as e:
            print(f"Failed to load {sym}: {e}")
            
    if not data:
        print("No data available.")
        return
        
    base_dates = list(data.values())[0].index
    
    initial_capital = 50000.0
    capital_per_coin = initial_capital / len(symbols)
    
    # Arb Parameters
    entry_apr_threshold = 0.30   # Enter when APR > 30%
    exit_apr_threshold = 0.10    # Exit when APR < 10%
    
    fee_spot = 0.001    # 0.1% spot fee
    fee_perp = 0.0005   # 0.05% perp taker fee
    
    portfolio = {
        sym: {
            'status': 'FLAT',
            'free_cash': capital_per_coin,
            'spot_qty': 0.0,
            'perp_qty': 0.0,
            'entry_price': 0.0
        } for sym in symbols
    }
    
    equity_curve = []
    dates_curve = []
    total_trades = 0
    
    print("\nExecuting Cash & Carry simulation...")
    
    for t in range(len(base_dates)):
        current_time = base_dates[t]
        current_total_equity = 0.0
        
        for sym in symbols:
            if sym not in data: continue
            df = data[sym]
            if current_time not in df.index: continue
            
            idx = df.index.get_loc(current_time)
            
            curr_close = df['Close'].iloc[idx]
            curr_apr = df['simulated_apr'].iloc[idx]
            
            # Since we evaluate at Close, our logic effectively simulates execution at Close or next Open. 
            # We use curr_close for valuation and execution for simplicity in an 8h structural model.
            
            port = portfolio[sym]
            
            if port['status'] == 'IN_ARB':
                # 1. Accrue Funding (1 epoch = 8 hours)
                # Funding rate per 8h = APR / (3 * 365)
                funding_payment = port['perp_qty'] * curr_close * (curr_apr / 1095.0)
                port['free_cash'] += funding_payment
                
                # 2. Check Exit Condition
                if curr_apr < exit_apr_threshold:
                    # Unwind positions
                    spot_value = port['spot_qty'] * curr_close
                    perp_pnl = port['perp_qty'] * (port['entry_price'] - curr_close)
                    
                    spot_fee = spot_value * fee_spot
                    perp_fee = (port['perp_qty'] * curr_close) * fee_perp
                    
                    port['free_cash'] += spot_value - spot_fee
                    port['free_cash'] += perp_pnl - perp_fee
                    
                    port['spot_qty'] = 0.0
                    port['perp_qty'] = 0.0
                    port['entry_price'] = 0.0
                    port['status'] = 'FLAT'
                    total_trades += 1
            
            elif port['status'] == 'FLAT':
                # 1. Check Entry Condition
                if curr_apr > entry_apr_threshold:
                    # Allocate capital: 50% to buy spot, 50% to collateralize perp short
                    notional = port['free_cash'] * 0.49 # Use 49% to leave room for fees and safety margin
                    
                    qty = notional / curr_close
                    
                    spot_fee = notional * fee_spot
                    perp_fee = notional * fee_perp
                    
                    port['free_cash'] -= notional + spot_fee + perp_fee
                    port['spot_qty'] = qty
                    port['perp_qty'] = qty
                    port['entry_price'] = curr_close
                    port['status'] = 'IN_ARB'
            
            # Calculate Mark-to-Market Equity for this coin
            coin_equity = port['free_cash']
            if port['status'] == 'IN_ARB':
                spot_value = port['spot_qty'] * curr_close
                perp_pnl = port['perp_qty'] * (port['entry_price'] - curr_close)
                coin_equity += spot_value + perp_pnl
                
            current_total_equity += coin_equity
            
        equity_curve.append(current_total_equity)
        dates_curve.append(current_time)
        
    # Force close all positions at the end
    final_equity = 0.0
    for sym in symbols:
        if sym not in data: continue
        port = portfolio[sym]
        last_close = data[sym]['Close'].iloc[-1]
        
        coin_equity = port['free_cash']
        if port['status'] == 'IN_ARB':
            spot_value = port['spot_qty'] * last_close
            perp_pnl = port['perp_qty'] * (port['entry_price'] - last_close)
            
            spot_fee = spot_value * fee_spot
            perp_fee = (port['perp_qty'] * last_close) * fee_perp
            
            coin_equity += spot_value + perp_pnl - spot_fee - perp_fee
            
        final_equity += coin_equity

    # Calculate Performance Metrics
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
        print(f"      BASIS ARBITRAGE FINAL PERFORMANCE TEAR SHEET")
        print(f"=====================================================")
        print(f"Initial Capital:  ${initial_capital:,.2f}")
        print(f"Final Equity:     ${final_equity:,.2f}")
        print(f"Total Arb Trades: {total_trades}")
        print(f"-----------------------------------------------------")
        print(f"Net Return:       {net_return*100:.2f}%")
        print(f"CAGR:             {cagr*100:.2f}%")
        print(f"Max Drawdown:     {max_drawdown*100:.2f}%")
        print(f"Sharpe Ratio:     {sharpe:.2f}")
        print(f"=====================================================\n")

if __name__ == "__main__":
    run_funding_arb_backtest()
