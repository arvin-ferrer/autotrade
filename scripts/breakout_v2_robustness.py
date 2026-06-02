"""
V2 Breakout Robustness Study
=============================
Tests the EXACT V2 bidirectional backtest engine across:
  - 3 timeframes: 1h, 4h, 1d
  - 4 market regimes:
      Bear:   2022-01-01 → 2022-12-31
      Bull:   2023-01-01 → 2024-12-31
      Recent: 2025-01-01 → 2026-06-01
      Full:   2022-01-01 → 2026-06-01

All simulations use identical parameters:
  Donchian=20, vol_threshold=1.2, stop=2*ATR, TP=10*ATR
  Fees=0.05%, Slippage=0.05%, Funding=0.01%/8h
  Inverse-ATR Risk Parity sizing (1% risk per trade)
  Max leverage: 2x per coin
"""

import os, sys, csv
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.loader import get_ohlcv
from strategies.breakout import AdaptiveHighBetaBreakoutStrategy


SYMBOLS = ['SOL/USDT', 'DOGE/USDT', 'ADA/USDT', 'LINK/USDT', 'DOT/USDT']
TIMEFRAMES = ['1h', '4h', '1d']
REGIMES = {
    'Bear 2022':       ('2022-01-01', '2022-12-31'),
    'Bull 2023-2024':  ('2023-01-01', '2024-12-31'),
    'Recent 2025-26':  ('2025-01-01', '2026-06-01'),
    'Full Period':     ('2022-01-01', '2026-06-01'),
}

# Backtest parameters (identical to V2 main backtest)
FEE_RATE       = 0.0005
SLIPPAGE_RATE  = 0.0005
FUNDING_RATE   = 0.0001
STOP_MULT      = 2.0
TP_MULT        = 10.0
RISK_PCT       = 0.01
MAX_LEV        = 2.0
INITIAL_CAPITAL = 10000.0


def run_single_backtest(sig_data_full: dict, start: str, end: str, timeframe: str):
    """
    Run the V2 backtest engine on a specific date range.
    sig_data_full: dict of sym -> full DataFrame with signals already generated.
    Returns a dict of metrics.
    """
    # Slice to regime
    regime_sig_data = {}
    for sym, df in sig_data_full.items():
        mask = (df.index >= start) & (df.index <= end)
        regime_df = df.loc[mask]
        if not regime_df.empty:
            regime_sig_data[sym] = regime_df

    # Build unified timeline
    all_dates = pd.DatetimeIndex([])
    for df in regime_sig_data.values():
        all_dates = all_dates.union(df.index)
    base_dates = all_dates.sort_values()

    if len(base_dates) < 10:
        return None  # Not enough data

    # Initialize portfolio
    free_cash = INITIAL_CAPITAL
    last_total_equity = INITIAL_CAPITAL

    portfolio = {
        sym: {
            'status': 'FLAT', 'qty': 0.0, 'entry_price': 0.0,
            'extreme_close': 0.0, 'trailing_stop_price': 0.0,
            'take_profit_price': 0.0
        } for sym in SYMBOLS
    }

    # Benchmark
    benchmark_qty = {sym: 0.0 for sym in SYMBOLS}
    alloc_per_coin = INITIAL_CAPITAL / len(SYMBOLS)
    for sym in SYMBOLS:
        if sym in regime_sig_data and len(regime_sig_data[sym]) > 0:
            first_open = regime_sig_data[sym]['Open'].iloc[0]
            if first_open > 0:
                benchmark_qty[sym] = alloc_per_coin / first_open

    equity_curve = []
    bh_curve = []
    dates_curve = []
    total_trades = 0
    winning_trades = 0

    for t in range(1, len(base_dates)):
        current_time = base_dates[t]

        # Benchmark MTM
        bh_equity = 0.0
        for sym in SYMBOLS:
            if sym in regime_sig_data and current_time in regime_sig_data[sym].index:
                bh_equity += benchmark_qty[sym] * regime_sig_data[sym]['Close'].loc[current_time]
        if bh_equity > 0:
            bh_curve.append(bh_equity)
        elif len(bh_curve) > 0:
            bh_curve.append(bh_curve[-1])
        else:
            bh_curve.append(INITIAL_CAPITAL)

        # Process each symbol
        for sym in SYMBOLS:
            if sym not in regime_sig_data:
                continue
            df = regime_sig_data[sym]
            if current_time not in df.index:
                continue

            idx = df.index.get_loc(current_time)
            if idx == 0:
                continue

            prev_signal = df['Signal'].iloc[idx - 1]
            prev_atr = df['atr'].iloc[idx - 1]

            curr_open = df['Open'].iloc[idx]
            curr_high = df['High'].iloc[idx]
            curr_low  = df['Low'].iloc[idx]
            curr_close = df['Close'].iloc[idx]
            curr_atr = df['atr'].iloc[idx]

            port = portfolio[sym]

            # Funding (0, 8, 16 UTC)
            if current_time.hour in [0, 8, 16]:
                if port['status'] == 'LONG':
                    free_cash -= port['qty'] * curr_open * FUNDING_RATE
                elif port['status'] == 'SHORT':
                    free_cash += port['qty'] * curr_open * FUNDING_RATE

            # ---------- FLAT: Look for entries ----------
            if port['status'] == 'FLAT':
                if not pd.isna(prev_atr) and prev_atr > 0:
                    risk_amount = last_total_equity * RISK_PCT

                    if prev_signal == 1.0:
                        exec_price = curr_open * (1 + SLIPPAGE_RATE)
                        qty = risk_amount / (STOP_MULT * prev_atr)
                        max_qty = (last_total_equity * MAX_LEV / len(SYMBOLS)) / exec_price
                        qty = min(qty, max_qty)

                        notional = qty * exec_price
                        fee = notional * FEE_RATE
                        free_cash -= notional + fee

                        port['qty'] = qty
                        port['entry_price'] = exec_price
                        port['extreme_close'] = curr_close
                        port['trailing_stop_price'] = exec_price - (STOP_MULT * prev_atr)
                        port['take_profit_price'] = exec_price + (TP_MULT * prev_atr)
                        port['status'] = 'LONG'

                    elif prev_signal == -1.0:
                        exec_price = curr_open * (1 - SLIPPAGE_RATE)
                        qty = risk_amount / (STOP_MULT * prev_atr)
                        max_qty = (last_total_equity * MAX_LEV / len(SYMBOLS)) / exec_price
                        qty = min(qty, max_qty)

                        notional = qty * exec_price
                        fee = notional * FEE_RATE
                        free_cash -= notional + fee

                        port['qty'] = qty
                        port['entry_price'] = exec_price
                        port['extreme_close'] = curr_close
                        port['trailing_stop_price'] = exec_price + (STOP_MULT * prev_atr)
                        port['take_profit_price'] = exec_price - (TP_MULT * prev_atr)
                        port['status'] = 'SHORT'

            # ---------- LONG: Check exits ----------
            elif port['status'] == 'LONG':
                exit_triggered = False
                exit_price = 0.0

                if prev_signal == -1.0:
                    exit_triggered = True
                    exit_price = curr_open * (1 - SLIPPAGE_RATE)
                elif curr_low <= port['trailing_stop_price']:
                    exit_triggered = True
                    actual_fill = min(curr_open, port['trailing_stop_price'])
                    exit_price = actual_fill * (1 - SLIPPAGE_RATE)
                elif curr_high >= port['take_profit_price']:
                    exit_triggered = True
                    actual_fill = max(curr_open, port['take_profit_price'])
                    exit_price = actual_fill * (1 - SLIPPAGE_RATE)

                if exit_triggered:
                    proceeds = port['qty'] * exit_price
                    fee = proceeds * FEE_RATE
                    free_cash += proceeds - fee

                    pnl = proceeds - fee - (port['qty'] * port['entry_price'])
                    if pnl > 0:
                        winning_trades += 1
                    total_trades += 1

                    port['qty'] = 0.0
                    port['status'] = 'FLAT'
                else:
                    port['extreme_close'] = max(port['extreme_close'], curr_close)
                    new_ts = port['extreme_close'] - (STOP_MULT * curr_atr)
                    port['trailing_stop_price'] = max(port['trailing_stop_price'], new_ts)

            # ---------- SHORT: Check exits ----------
            elif port['status'] == 'SHORT':
                exit_triggered = False
                exit_price = 0.0

                if prev_signal == 1.0:
                    exit_triggered = True
                    exit_price = curr_open * (1 + SLIPPAGE_RATE)
                elif curr_high >= port['trailing_stop_price']:
                    exit_triggered = True
                    actual_fill = max(curr_open, port['trailing_stop_price'])
                    exit_price = actual_fill * (1 + SLIPPAGE_RATE)
                elif curr_low <= port['take_profit_price']:
                    exit_triggered = True
                    actual_fill = min(curr_open, port['take_profit_price'])
                    exit_price = actual_fill * (1 + SLIPPAGE_RATE)

                if exit_triggered:
                    cost = port['qty'] * exit_price
                    fee = cost * FEE_RATE
                    pnl = (port['entry_price'] - exit_price) * port['qty']
                    free_cash += (port['entry_price'] * port['qty']) + pnl - fee

                    if pnl - fee > 0:
                        winning_trades += 1
                    total_trades += 1

                    port['qty'] = 0.0
                    port['status'] = 'FLAT'
                else:
                    port['extreme_close'] = min(port['extreme_close'], curr_close)
                    new_ts = port['extreme_close'] + (STOP_MULT * curr_atr)
                    port['trailing_stop_price'] = min(port['trailing_stop_price'], new_ts)

        # End-of-bar MTM equity
        eod_equity = free_cash
        for sym in SYMBOLS:
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

    # Final liquidation
    final_equity = free_cash
    final_bh_equity = 0.0

    for sym in SYMBOLS:
        port = portfolio[sym]
        if sym in regime_sig_data:
            last_close = regime_sig_data[sym]['Close'].iloc[-1]
            final_bh_equity += benchmark_qty[sym] * last_close

            if port['status'] == 'LONG':
                proceeds = port['qty'] * last_close
                fee = proceeds * FEE_RATE
                final_equity += proceeds - fee
            elif port['status'] == 'SHORT':
                cost = port['qty'] * last_close
                fee = cost * FEE_RATE
                pnl = (port['entry_price'] - last_close) * port['qty']
                final_equity += (port['entry_price'] * port['qty']) + pnl - fee

    # Compute metrics
    if len(equity_curve) < 2:
        return None

    equity_series = pd.Series(equity_curve, index=dates_curve)
    bh_series = pd.Series(bh_curve, index=dates_curve)

    peak = equity_series.expanding(min_periods=1).max()
    drawdown = (equity_series - peak) / peak
    max_drawdown = drawdown.min()

    net_return = (final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL
    days = (dates_curve[-1] - dates_curve[0]).days
    cagr = (final_equity / INITIAL_CAPITAL) ** (365.25 / days) - 1 if days > 0 else 0

    daily_equity = equity_series.resample('1D').last().dropna()
    returns = daily_equity.pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * np.sqrt(365.25) if returns.std() != 0 else 0

    win_rate = (winning_trades / total_trades) if total_trades > 0 else 0

    bh_net_return = (final_bh_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL
    bh_cagr = (final_bh_equity / INITIAL_CAPITAL) ** (365.25 / days) - 1 if days > 0 else 0

    bh_peak = bh_series.expanding(min_periods=1).max()
    bh_drawdown = (bh_series - bh_peak) / bh_peak
    bh_max_dd = bh_drawdown.min()

    bh_daily = bh_series.resample('1D').last().dropna()
    bh_rets = bh_daily.pct_change().dropna()
    bh_sharpe = (bh_rets.mean() / bh_rets.std()) * np.sqrt(365.25) if bh_rets.std() != 0 else 0

    return {
        'final_equity': final_equity,
        'net_return': net_return,
        'cagr': cagr,
        'max_drawdown': max_drawdown,
        'sharpe': sharpe,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'bh_net_return': bh_net_return,
        'bh_cagr': bh_cagr,
        'bh_max_dd': bh_max_dd,
        'bh_sharpe': bh_sharpe,
    }


def main():
    strategy = AdaptiveHighBetaBreakoutStrategy(params={
        'atr_window': 14,
        'baseline_window': 50,
        'donchian_window': 20,
        'vol_threshold': 1.2
    })

    results = []

    for tf in TIMEFRAMES:
        print(f"\n{'='*60}")
        print(f"  LOADING DATA: Timeframe = {tf}")
        print(f"{'='*60}")

        # Pre-load all data for this timeframe (with warmup from 2021)
        raw_data = {}
        for sym in SYMBOLS:
            try:
                df = get_ohlcv(sym, tf, '2021-01-01', '2026-06-01')
                if not df.empty:
                    raw_data[sym] = df[~df.index.duplicated(keep='first')]
                    print(f"  ✓ {sym}: {len(raw_data[sym])} candles")
            except Exception as e:
                print(f"  ✗ {sym}: {e}")

        if not raw_data:
            print(f"  No data for {tf}. Skipping.")
            continue

        # Generate signals once (includes warmup period)
        sig_data_full = {}
        for sym, df in raw_data.items():
            sig_data_full[sym] = strategy.generate_signals(df)

        # Run each market regime
        for regime_name, (start, end) in REGIMES.items():
            print(f"\n  Running: {tf} | {regime_name} ({start} → {end})...")

            metrics = run_single_backtest(sig_data_full, start, end, tf)

            if metrics is None:
                print(f"    ⚠ Insufficient data. Skipped.")
                row = {
                    'Timeframe': tf, 'Regime': regime_name,
                    'Net Return': 'N/A', 'Max Drawdown': 'N/A',
                    'Sharpe': 'N/A', 'Trades': 0, 'Win Rate': 'N/A',
                    'BH Return': 'N/A', 'BH Sharpe': 'N/A',
                    'Beats BH': 'N/A'
                }
            else:
                beats_bh = metrics['net_return'] > metrics['bh_net_return']
                row = {
                    'Timeframe': tf,
                    'Regime': regime_name,
                    'Net Return': f"{metrics['net_return']*100:.2f}%",
                    'CAGR': f"{metrics['cagr']*100:.2f}%",
                    'Max Drawdown': f"{metrics['max_drawdown']*100:.2f}%",
                    'Sharpe': f"{metrics['sharpe']:.2f}",
                    'Trades': metrics['total_trades'],
                    'Win Rate': f"{metrics['win_rate']*100:.1f}%",
                    'BH Return': f"{metrics['bh_net_return']*100:.2f}%",
                    'BH Max DD': f"{metrics['bh_max_dd']*100:.2f}%",
                    'BH Sharpe': f"{metrics['bh_sharpe']:.2f}",
                    'Beats BH': '✅ YES' if beats_bh else '❌ NO'
                }
                print(f"    Return: {row['Net Return']} | Sharpe: {row['Sharpe']} | "
                      f"Trades: {row['Trades']} | Win: {row['Win Rate']} | "
                      f"vs BH: {row['BH Return']} | {row['Beats BH']}")

            results.append(row)

    # Save CSV
    csv_path = os.path.join(os.path.dirname(__file__), 'breakout_v2_robustness_results.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\n✅ Results saved to {csv_path}")

    # Print final summary table
    print(f"\n{'='*100}")
    print(f"  V2 BREAKOUT ROBUSTNESS MATRIX — ALL TIMEFRAMES × ALL REGIMES")
    print(f"{'='*100}")
    header = f"{'TF':<6} | {'Regime':<18} | {'Return':>10} | {'CAGR':>10} | {'MaxDD':>10} | {'Sharpe':>7} | {'Trades':>7} | {'WinR':>7} | {'BH Ret':>10} | {'Beat BH':>8}"
    print(header)
    print('-' * 100)
    for r in results:
        line = (f"{r['Timeframe']:<6} | {r['Regime']:<18} | "
                f"{r.get('Net Return','N/A'):>10} | {r.get('CAGR','N/A'):>10} | "
                f"{r.get('Max Drawdown','N/A'):>10} | {r.get('Sharpe','N/A'):>7} | "
                f"{r.get('Trades',0):>7} | {r.get('Win Rate','N/A'):>7} | "
                f"{r.get('BH Return','N/A'):>10} | {r.get('Beats BH','N/A'):>8}")
        print(line)
    print('=' * 100)


if __name__ == '__main__':
    main()
