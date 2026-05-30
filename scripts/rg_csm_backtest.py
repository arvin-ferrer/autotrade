import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.loader import get_ohlcv

def compute_drawdown(equity_curve):
    peak = equity_curve.cummax()
    drawdown = (equity_curve - peak) / peak
    return drawdown.min()

def compute_cagr(start_val, end_val, days):
    return (end_val / start_val) ** (365.25 / days) - 1

def compute_sharpe(returns, risk_free=0.0):
    if returns.std() == 0: return 0
    return (returns.mean() - risk_free) / returns.std() * np.sqrt(365.25)

import argparse

def run_rg_csm_backtest():
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
    print(f" RIGOROUS RG-CSM BACKTEST ENGINE ({timeframe})")
    print(f" Period: {start_date} to {end_date}")
    print("=====================================================")
    
    data = {}
    for sym in symbols:
        try:
            df = get_ohlcv(sym, timeframe, start_date, end_date)
            if not df.empty: data[sym] = df
        except Exception: pass
            
    if 'BTC/USDT' not in data: return
        
    close_prices = pd.DataFrame({sym: df['Close'] for sym, df in data.items()}).dropna(how='all')
    open_prices = pd.DataFrame({sym: df['Open'] for sym, df in data.items()}).dropna(how='all')
    high_prices = pd.DataFrame({sym: df['High'] for sym, df in data.items()}).dropna(how='all')
    low_prices = pd.DataFrame({sym: df['Low'] for sym, df in data.items()}).dropna(how='all')
    
    # 2. MACRO GATE MATH
    btc_close = close_prices['BTC/USDT']
    btc_sma = btc_close.rolling(100).mean()
    gate_open = pd.Series(index=btc_close.index, dtype=bool)
    current_gate_state = False
    
    for i in range(len(btc_close)):
        close_val = btc_close.iloc[i]
        sma_val = btc_sma.iloc[i]
        if pd.isna(sma_val):
            gate_open.iloc[i] = False
            continue
        if not current_gate_state and close_val > sma_val * 1.02:
            current_gate_state = True
        elif current_gate_state and close_val < sma_val * 0.98:
            current_gate_state = False
        gate_open.iloc[i] = current_gate_state

    # 3. ALPHA GENERATION MATH
    returns_90d = close_prices.pct_change(90)
    daily_returns = close_prices.pct_change(1)
    std_90d = daily_returns.rolling(90).std()
    mom_scores = returns_90d / std_90d
    
    # 4. RISK MANAGEMENT (ATR)
    atr_dict = {}
    for sym in close_prices.columns:
        high_low = high_prices[sym] - low_prices[sym]
        high_cp = (high_prices[sym] - close_prices[sym].shift()).abs()
        low_cp = (low_prices[sym] - close_prices[sym].shift()).abs()
        tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
        atr_dict[sym] = tr.ewm(alpha=1/14, adjust=False).mean()
    atr_df = pd.DataFrame(atr_dict)
    
    # EXECUTION ENGINE
    initial_cash = 10000.0
    cash = initial_cash
    fee = 0.002 
    
    portfolio = {} 
    equity_curve = []
    
    trades_won = 0
    trades_lost = 0
    
    start_idx = 100 
    dates = close_prices.index
    
    print("Executing look-ahead-bias-free backtest...")
    
    for i in range(start_idx, len(dates)):
        current_date = dates[i]
        
        # LOOK-AHEAD BIAS FIX: Evaluate yesterday's signals to execute today
        macro_open_yesterday = gate_open.iloc[i-1]
        
        # Ensures exactly one weekly rebalance regardless of timeframe (triggers on first candle of Monday)
        is_sunday_yesterday = (dates[i-1].weekday() == 6 and dates[i].weekday() == 0)
        
        # 1. Update Trailing Stops & Emergency Exits (Checked DAILY)
        to_remove = []
        for sym, pos in list(portfolio.items()):
            curr_low = low_prices[sym].iloc[i]
            curr_high = high_prices[sym].iloc[i]
            curr_open = open_prices[sym].iloc[i]
            
            if pd.isna(curr_open): continue
            
            # LOOK-AHEAD FIX: Calculate today's stop using YESTERDAY'S ATR
            new_stop = pos['highest'] - 3.0 * atr_df[sym].iloc[i-1]
            pos['stop'] = max(pos['stop'], new_stop)
            
            # Condition A: Market crashes mid-week. Execute at Open.
            if not macro_open_yesterday:
                value = pos['shares'] * curr_open
                cash += value * (1 - fee)
                to_remove.append((sym, curr_open))
            # Condition B: INTRADAY STOP LOSS FIX (Checked against Low, not Close)
            elif curr_low <= pos['stop']:
                fill_price = min(pos['stop'], curr_open) if curr_open < pos['stop'] else pos['stop']
                value = pos['shares'] * fill_price
                cash += value * (1 - fee)
                to_remove.append((sym, fill_price))
                
            pos['highest'] = max(pos['highest'], curr_high)
                
        for sym, fill_price in to_remove:
            if fill_price > portfolio[sym]['entry_price']: trades_won += 1
            else: trades_lost += 1
            del portfolio[sym]
            
        # 2. Rebalance (Delta Rebalancing to save fees)
        if is_sunday_yesterday and macro_open_yesterday:
            scores = mom_scores.iloc[i-1].dropna()
            positive_scores = scores[returns_90d.iloc[i-1][scores.index] > 0]
            top3 = positive_scores.sort_values(ascending=False).head(3).index.tolist()
            
            # Sell assets no longer in top 3
            to_sell = [sym for sym in portfolio.keys() if sym not in top3]
            for sym in to_sell:
                curr_open = open_prices[sym].iloc[i]
                if pd.isna(curr_open): continue
                value = portfolio[sym]['shares'] * curr_open
                cash += value * (1 - fee)
                if curr_open > portfolio[sym]['entry_price']: trades_won += 1
                else: trades_lost += 1
                del portfolio[sym]
                
            # Rebalance Top 3
            if len(top3) > 0:
                total_value = cash + sum(portfolio[s]['shares'] * open_prices[s].iloc[i] for s in portfolio if not pd.isna(open_prices[s].iloc[i]))
                target_value = total_value / 3.0
                
                # First sell excess
                for sym in list(portfolio.keys()):
                    curr_open = open_prices[sym].iloc[i]
                    if pd.isna(curr_open): continue
                    current_value = portfolio[sym]['shares'] * curr_open
                    if current_value > target_value:
                        excess = current_value - target_value
                        portfolio[sym]['shares'] -= excess / curr_open
                        cash += excess * (1 - fee)
                        
                # Then buy deficit
                for sym in top3:
                    curr_open = open_prices[sym].iloc[i]
                    if pd.isna(curr_open): continue
                    if sym in portfolio:
                        current_value = portfolio[sym]['shares'] * curr_open
                        if current_value < target_value:
                            deficit = min(target_value - current_value, cash)
                            portfolio[sym]['shares'] += (deficit * (1 - fee)) / curr_open
                            cash -= deficit
                    else:
                        deficit = min(target_value, cash)
                        portfolio[sym] = {
                            'shares': (deficit * (1 - fee)) / curr_open,
                            'entry_price': curr_open,
                            'highest': curr_open,
                            'stop': curr_open - 3.0 * atr_df[sym].iloc[i-1]
                        }
                        cash -= deficit

        # Record daily equity
        current_eq = cash
        for sym, pos in portfolio.items():
            curr_close = close_prices[sym].iloc[i]
            if not pd.isna(curr_close):
                current_eq += pos['shares'] * curr_close
        equity_curve.append(current_eq)
        
    eq_series = pd.Series(equity_curve, index=dates[start_idx:])
    daily_rets = eq_series.pct_change().dropna()
    
    total_trades = trades_won + trades_lost
    win_rate = (trades_won / total_trades * 100) if total_trades > 0 else 0
    cagr = compute_cagr(initial_cash, eq_series.iloc[-1], len(eq_series))
    mdd = compute_drawdown(eq_series)
    sharpe = compute_sharpe(daily_rets)
    
    print("\n=====================================================")
    print("      RG-CSM FINAL PERFORMANCE TEAR SHEET (FIXED)")
    print("=====================================================")
    print(f"Test Period:      {dates[start_idx].date()} to {dates[-1].date()}")
    print(f"Initial Capital:  ${initial_cash:,.2f}")
    print(f"Final Equity:     ${eq_series.iloc[-1]:,.2f}")
    print("-----------------------------------------------------")
    print(f"Net Return:       {(eq_series.iloc[-1]/initial_cash - 1)*100:+.2f}%")
    print(f"CAGR:             {cagr*100:+.2f}%")
    print(f"Max Drawdown:     {mdd*100:.2f}%")
    print(f"Sharpe Ratio:     {sharpe:.2f}")
    print(f"Win Rate:         {win_rate:.1f}% ({trades_won}W / {trades_lost}L)")
    print("=====================================================")

if __name__ == "__main__":
    run_rg_csm_backtest()
