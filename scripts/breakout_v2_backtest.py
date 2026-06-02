import os
import sys
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.loader import get_ohlcv
from strategies.breakout import AdaptiveHighBetaBreakoutStrategy

def run_v2_backtest():
    symbols = ['SOL/USDT', 'DOGE/USDT', 'ADA/USDT', 'LINK/USDT', 'DOT/USDT']
    start_date = '2022-01-01'
    end_date = '2026-06-01'
    timeframe = '4h'
    
    print("=====================================================")
    print(" V2 BREAKOUT BACKTEST (BIDIRECTIONAL + PERPS + ATR SIZE)")
    print(f" Period: {start_date} to {end_date} | Timeframe: {timeframe}")
    print("=====================================================")
    
    strategy = AdaptiveHighBetaBreakoutStrategy(params={
        'atr_window': 14,
        'baseline_window': 50,
        'donchian_window': 20,
        'vol_threshold': 1.2
    })
    
    raw_data = {}
    for sym in symbols:
        try:
            print(f"Loading {sym}...")
            # Load from 2021 to warm up indicators
            df = get_ohlcv(sym, timeframe, '2021-01-01', end_date)
            if not df.empty:
                raw_data[sym] = df[~df.index.duplicated(keep='first')]
        except Exception as e:
            pass
            
    if not raw_data:
        return
        
    sig_data = {}
    for sym, df in raw_data.items():
        sig_data[sym] = strategy.generate_signals(df)
        
    regime_sig_data = {}
    for sym, df in sig_data.items():
        mask = (df.index >= start_date) & (df.index <= end_date)
        regime_df = df.loc[mask]
        if not regime_df.empty:
            regime_sig_data[sym] = regime_df
            
    all_dates = pd.DatetimeIndex([])
    for df in regime_sig_data.values():
        all_dates = all_dates.union(df.index)
    base_dates = all_dates.sort_values()
    
    if len(base_dates) == 0:
        return
        
    initial_capital = 10000.0
    free_cash = initial_capital
    last_total_equity = initial_capital
    
    portfolio = {
        sym: {
            'status': 'FLAT',
            'qty': 0.0,
            'entry_price': 0.0,
            'extreme_close': 0.0, 
            'trailing_stop_price': 0.0,
            'take_profit_price': 0.0
        } for sym in symbols
    }
    
    # Benchmarking
    benchmark_qty = {sym: 0.0 for sym in symbols}
    alloc_per_coin = initial_capital / len(symbols)
    for sym in symbols:
        if sym in regime_sig_data and len(regime_sig_data[sym]) > 0:
            first_open = regime_sig_data[sym]['Open'].iloc[0]
            benchmark_qty[sym] = alloc_per_coin / first_open
    
    fee_rate = 0.0005       
    slippage_rate = 0.0005 
    funding_rate = 0.0001
    
    stop_mult = 2.0
    tp_mult = 10.0
    risk_pct = 0.01
    max_leverage_per_coin = 2.0
    
    equity_curve = []
    bh_curve = []
    dates_curve = []
    total_trades = 0
    winning_trades = 0
    
    for t in range(1, len(base_dates)):
        current_time = base_dates[t]
        
        # Benchmark MTM
        bh_equity = 0.0
        for sym in symbols:
            if sym in regime_sig_data and current_time in regime_sig_data[sym].index:
                curr_close = regime_sig_data[sym]['Close'].loc[current_time]
                bh_equity += benchmark_qty[sym] * curr_close
            else:
                # If coin is missing for this candle, use last known value if possible
                pass
        # Better BH MTM logic (using forward fill would be best, but for active bars it works)
        if bh_equity > 0:
            bh_curve.append(bh_equity)
        elif len(bh_curve) > 0:
            bh_curve.append(bh_curve[-1])
        else:
            bh_curve.append(initial_capital)
        
        # Process Execution
        for sym in symbols:
            if sym not in regime_sig_data: continue
            df = regime_sig_data[sym]
            if current_time not in df.index: continue
            
            idx = df.index.get_loc(current_time)
            if idx == 0: continue
            
            prev_signal = df['Signal'].iloc[idx-1]
            prev_atr = df['atr'].iloc[idx-1]
            
            curr_open = df['Open'].iloc[idx]
            curr_high = df['High'].iloc[idx]
            curr_low = df['Low'].iloc[idx]
            curr_close = df['Close'].iloc[idx]
            curr_atr = df['atr'].iloc[idx]
            
            port = portfolio[sym]
            
            # Funding (0, 8, 16 UTC)
            if current_time.hour in [0, 8, 16]:
                if port['status'] == 'LONG':
                    free_cash -= port['qty'] * curr_open * funding_rate
                elif port['status'] == 'SHORT':
                    free_cash += port['qty'] * curr_open * funding_rate
            
            if port['status'] == 'FLAT':
                if not pd.isna(prev_atr):
                    # Risk dynamically scales using stable T-1 equity
                    risk_amount = last_total_equity * risk_pct
                    
                    if prev_signal == 1.0:
                        exec_price = curr_open * (1 + slippage_rate)
                        qty = risk_amount / (stop_mult * prev_atr)
                        max_qty = (last_total_equity * max_leverage_per_coin / len(symbols)) / exec_price
                        qty = min(qty, max_qty)
                        
                        notional = qty * exec_price
                        fee = notional * fee_rate
                        
                        free_cash -= notional + fee
                        port['qty'] = qty
                        port['entry_price'] = exec_price
                        port['extreme_close'] = curr_close
                        
                        port['trailing_stop_price'] = exec_price - (stop_mult * prev_atr)
                        port['take_profit_price'] = exec_price + (tp_mult * prev_atr)
                        port['status'] = 'LONG'
                        
                    elif prev_signal == -1.0:
                        exec_price = curr_open * (1 - slippage_rate)
                        qty = risk_amount / (stop_mult * prev_atr)
                        max_qty = (last_total_equity * max_leverage_per_coin / len(symbols)) / exec_price
                        qty = min(qty, max_qty)
                        
                        notional = qty * exec_price
                        fee = notional * fee_rate
                        
                        free_cash -= notional + fee 
                        port['qty'] = qty
                        port['entry_price'] = exec_price
                        port['extreme_close'] = curr_close
                        
                        port['trailing_stop_price'] = exec_price + (stop_mult * prev_atr)
                        port['take_profit_price'] = exec_price - (tp_mult * prev_atr)
                        port['status'] = 'SHORT'
                        
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
                    free_cash += proceeds - fee
                    
                    pnl = proceeds - fee - (port['qty'] * port['entry_price'])
                    if pnl > 0: winning_trades += 1
                    total_trades += 1
                    
                    port['qty'] = 0.0
                    port['status'] = 'FLAT'
                else:
                    port['extreme_close'] = max(port['extreme_close'], curr_close)
                    new_ts = port['extreme_close'] - (stop_mult * curr_atr)
                    port['trailing_stop_price'] = max(port['trailing_stop_price'], new_ts)
                    
            elif port['status'] == 'SHORT':
                exit_triggered = False
                exit_price = 0.0
                
                if prev_signal == 1.0:
                    exit_triggered = True
                    exit_price = curr_open * (1 + slippage_rate)
                elif curr_high >= port['trailing_stop_price']:
                    exit_triggered = True
                    actual_fill = max(curr_open, port['trailing_stop_price'])
                    exit_price = actual_fill * (1 + slippage_rate)
                elif curr_low <= port['take_profit_price']:
                    exit_triggered = True
                    actual_fill = min(curr_open, port['take_profit_price'])
                    exit_price = actual_fill * (1 + slippage_rate)
                    
                if exit_triggered:
                    cost = port['qty'] * exit_price
                    fee = cost * fee_rate
                    pnl = (port['entry_price'] - exit_price) * port['qty']
                    free_cash += (port['entry_price'] * port['qty']) + pnl - fee
                    
                    if pnl - fee > 0: winning_trades += 1
                    total_trades += 1
                    
                    port['qty'] = 0.0
                    port['status'] = 'FLAT'
                else:
                    port['extreme_close'] = min(port['extreme_close'], curr_close)
                    new_ts = port['extreme_close'] + (stop_mult * curr_atr)
                    port['trailing_stop_price'] = min(port['trailing_stop_price'], new_ts) 
                    
        # Update T-1 Equity State strictly at End-Of-Bar
        eod_equity = free_cash
        for sym in symbols:
            port = portfolio[sym]
            if sym in regime_sig_data and current_time in regime_sig_data[sym].index:
                curr_close = regime_sig_data[sym]['Close'].loc[current_time]
                if port['status'] == 'LONG':
                    pnl = (curr_close - port['entry_price']) * port['qty']
                    eod_equity += port['qty'] * port['entry_price'] + pnl
                elif port['status'] == 'SHORT':
                    pnl = (port['entry_price'] - curr_close) * port['qty']
                    eod_equity += port['qty'] * port['entry_price'] + pnl
                    
        last_total_equity = eod_equity
        equity_curve.append(eod_equity)
        dates_curve.append(current_time)
        
    final_equity = free_cash
    final_bh_equity = 0.0
    
    for sym in symbols:
        port = portfolio[sym]
        if sym in regime_sig_data:
            last_close = regime_sig_data[sym]['Close'].iloc[-1]
            final_bh_equity += benchmark_qty[sym] * last_close
            
            if port['status'] == 'LONG':
                proceeds = port['qty'] * last_close
                fee = proceeds * fee_rate
                final_equity += proceeds - fee
            elif port['status'] == 'SHORT':
                cost = port['qty'] * last_close
                fee = cost * fee_rate
                pnl = (port['entry_price'] - last_close) * port['qty']
                final_equity += (port['entry_price'] * port['qty']) + pnl - fee

    equity_series = pd.Series(equity_curve, index=dates_curve)
    bh_series = pd.Series(bh_curve, index=dates_curve)
    
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
        
        bh_peak = bh_series.expanding(min_periods=1).max()
        bh_drawdown = (bh_series - bh_peak) / bh_peak
        bh_max_drawdown = bh_drawdown.min()
        bh_net_return = (final_bh_equity - initial_capital) / initial_capital
        bh_cagr = (final_bh_equity / initial_capital) ** (365.25 / days) - 1 if days > 0 else 0
        
        bh_daily = bh_series.resample('1D').last().dropna()
        bh_returns = bh_daily.pct_change().dropna()
        bh_sharpe = (bh_returns.mean() / bh_returns.std()) * np.sqrt(365.25) if bh_returns.std() != 0 else 0
        
        print(f"\n=====================================================")
        print(f"      V2 BREAKOUT VS BUY & HOLD PERFORMANCE TEAR SHEET")
        print(f"=====================================================")
        print(f"Initial Capital:  ${initial_capital:,.2f}")
        print(f"Total Trades:     {total_trades}")
        print(f"Win Rate:         {win_rate*100:.1f}%")
        print(f"-----------------------------------------------------")
        print(f"METRIC            | V2 STRATEGY     | BUY & HOLD")
        print(f"-----------------------------------------------------")
        print(f"Final Equity      | ${final_equity:<13,.2f} | ${final_bh_equity:,.2f}")
        print(f"Net Return        | {net_return*100:<13.2f}% | {bh_net_return*100:.2f}%")
        print(f"CAGR              | {cagr*100:<13.2f}% | {bh_cagr*100:.2f}%")
        print(f"Max Drawdown      | {max_drawdown*100:<13.2f}% | {bh_max_drawdown*100:.2f}%")
        print(f"Sharpe Ratio      | {sharpe:<14.2f}| {bh_sharpe:.2f}")
        print(f"=====================================================\n")

if __name__ == "__main__":
    run_v2_backtest()
