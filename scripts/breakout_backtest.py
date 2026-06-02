import os
import sys
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.loader import get_ohlcv
from strategies.breakout import AdaptiveHighBetaBreakoutStrategy

def run_breakout_backtest():
    symbols = ['SOL/USDT', 'DOGE/USDT', 'ADA/USDT', 'LINK/USDT', 'DOT/USDT']
    start_date = '2024-01-01'
    end_date = '2026-06-01'
    timeframe = '4h'
    
    print("=====================================================")
    print(" HIGH-BETA VOLATILITY BREAKOUT BACKTEST")
    print(f" Period: {start_date} to {end_date} | Timeframe: {timeframe}")
    print("=====================================================")
    
    strategy = AdaptiveHighBetaBreakoutStrategy()
    
    data = {}
    for sym in symbols:
        try:
            print(f"Loading {sym}...")
            df = get_ohlcv(sym, timeframe, start_date, end_date)
            if not df.empty:
                df = df[~df.index.duplicated(keep='first')]
                df = strategy.generate_signals(df)
                data[sym] = df
        except Exception as e:
            print(f"Failed to load {sym}: {e}")
            
    if not data:
        print("No data available.")
        return
        
    base_dates = list(data.values())[0].index
    print("\nExecuting chronological simulation...")
    
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
    
    fee_rate = 0.001       # 0.1% spot fee
    slippage_rate = 0.0005 # 0.05% slippage
    
    atr_stop_multiplier = 2.0
    atr_tp_multiplier = 6.0
    
    equity_curve = []
    dates_curve = []
    total_trades = 0
    winning_trades = 0
    total_fees_paid = 0.0
    
    for t in range(1, len(base_dates)):
        current_time = base_dates[t]
        current_total_equity = 0.0
        
        for sym in symbols:
            if sym not in data: continue
            df = data[sym]
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
                    
                    initial_stop = exec_price - (atr_stop_multiplier * prev_atr)
                    port['take_profit_price'] = exec_price + (atr_tp_multiplier * prev_atr)
                    port['trailing_stop_price'] = initial_stop
                    
                    port['status'] = 'LONG'
                    total_fees_paid += fee
                    
            elif port['status'] == 'LONG':
                exit_triggered = False
                exit_price = 0.0
                exit_reason = ""
                
                # 1. Chronology fix: Trend exit executes at Open
                if prev_signal == -1.0:
                    exit_triggered = True
                    exit_price = curr_open * (1 - slippage_rate)
                    exit_reason = "Trend Exit"
                    
                # 2. Intraday Look-ahead fix: Check SL using Low
                elif curr_low <= port['trailing_stop_price']:
                    exit_triggered = True
                    actual_fill = min(curr_open, port['trailing_stop_price'])
                    exit_price = actual_fill * (1 - slippage_rate)
                    exit_reason = "Trailing Stop Loss"
                    
                # 3. Intraday Take Profit using High
                elif curr_high >= port['take_profit_price']:
                    exit_triggered = True
                    actual_fill = max(curr_open, port['take_profit_price'])
                    exit_price = actual_fill * (1 - slippage_rate)
                    exit_reason = "Take Profit"
                    
                if exit_triggered:
                    proceeds = port['qty'] * exit_price
                    fee = proceeds * fee_rate
                    port['free_cash'] += proceeds - fee
                    total_fees_paid += fee
                    
                    pnl = proceeds - fee - (port['qty'] * port['entry_price'])
                    if pnl > 0:
                        winning_trades += 1
                    total_trades += 1
                    
                    # Print log of the trade
                    print(f"[{current_time}] Closed {sym} | Entry: ${port['entry_price']:.4f} | Exit: ${exit_price:.4f} | PnL: ${pnl:+.2f} ({exit_reason})")
                    
                    port['qty'] = 0.0
                    port['status'] = 'FLAT'
                else:
                    # 4. End-of-Bar State Leakage Fix & Non-Monotonic Fix
                    port['highest_close'] = max(port['highest_close'], curr_close)
                    new_trailing_stop = port['highest_close'] - (atr_stop_multiplier * curr_atr)
                    port['trailing_stop_price'] = max(port['trailing_stop_price'], new_trailing_stop)
            
            coin_equity = port['free_cash']
            if port['status'] == 'LONG':
                coin_equity += port['qty'] * curr_close
            current_total_equity += coin_equity
            
        equity_curve.append(current_total_equity)
        dates_curve.append(current_time)
        
    final_equity = 0.0
    for sym in symbols:
        if sym not in data: continue
        port = portfolio[sym]
        last_close = data[sym]['Close'].iloc[-1]
        
        coin_equity = port['free_cash']
        if port['status'] == 'LONG':
            proceeds = port['qty'] * last_close
            fee = proceeds * fee_rate
            coin_equity += proceeds - fee
            total_fees_paid += fee
        final_equity += coin_equity

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
        
        win_rate = (winning_trades / total_trades) if total_trades > 0 else 0
        
        print(f"\n=====================================================")
        print(f"      BREAKOUT BACKTEST FINAL PERFORMANCE TEAR SHEET")
        print(f"=====================================================")
        print(f"Initial Capital:  ${initial_capital:,.2f}")
        print(f"Final Equity:     ${final_equity:,.2f}")
        print(f"Total Trades:     {total_trades}")
        print(f"Win Rate:         {win_rate*100:.1f}%")
        print(f"Total Fees Paid:  ${total_fees_paid:,.2f}")
        print(f"-----------------------------------------------------")
        print(f"Net Return:       {net_return*100:.2f}%")
        print(f"CAGR:             {cagr*100:.2f}%")
        print(f"Max Drawdown:     {max_drawdown*100:.2f}%")
        print(f"Sharpe Ratio:     {sharpe:.2f}")
        print(f"=====================================================\n")

if __name__ == "__main__":
    run_breakout_backtest()
