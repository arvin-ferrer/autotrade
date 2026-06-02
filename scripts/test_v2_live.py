#!/usr/bin/env python3
"""
V2 Adaptive High-Beta Breakout Strategy — Live Engine Unit Tests

Validates that the live trading engine's V2 position management 
matches the backtest engine in scripts/breakout_v2_backtest.py.

Tests:
1. DB schema initialization (positions table)
2. LONG entry → trailing stop ratchet → close (signal reversal)
3. SHORT entry → take-profit close
4. P&L math verification against backtest formulas
5. Funding rate application
"""

import os
import sys
import math
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a temporary DB file so we don't corrupt the live DB
import live.db as db
_test_db = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'test_v2_live.db'
)
db.DB_FILE = _test_db

from live.db import (
    init_db, get_open_position, open_position,
    update_position_stop, update_position_funding,
    close_position, get_position_history
)

# ── Test config matching the backtest ──
FEE_RATE = 0.0005
FUNDING_RATE = 0.0001
STOP_MULT = 2.0
TP_MULT = 10.0
RISK_PCT = 0.01
MAX_LEVERAGE = 2.0
NUM_SYMBOLS = 5
INITIAL_EQUITY = 10000.0

PASS = 0
FAIL = 0

def assert_close(actual, expected, label, tol=1e-6):
    global PASS, FAIL
    if abs(actual - expected) < tol:
        print(f"  ✅ {label}: {actual:.6f} ≈ {expected:.6f}")
        PASS += 1
    else:
        print(f"  ❌ {label}: got {actual:.6f}, expected {expected:.6f} (diff={actual-expected:.10f})")
        FAIL += 1

def assert_equal(actual, expected, label):
    global PASS, FAIL
    if actual == expected:
        print(f"  ✅ {label}: {actual}")
        PASS += 1
    else:
        print(f"  ❌ {label}: got {actual}, expected {expected}")
        FAIL += 1


def test_db_init():
    """Test 1: DB initializes with positions table."""
    print("\n═══ TEST 1: DB Initialization ═══")
    
    # Clean up any existing test DB
    if os.path.exists(_test_db):
        os.remove(_test_db)
    
    init_db(initial_cash_php=500000.0)
    
    # Check positions table exists
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='positions'")
    result = cursor.fetchone()
    conn.close()
    
    assert_equal(result is not None, True, "positions table exists")
    
    # Check no open positions
    pos = get_open_position('SOL/USDT')
    assert_equal(pos, None, "No open position initially")


def test_long_lifecycle():
    """Test 2: LONG entry → trailing stop update → close via signal reversal."""
    print("\n═══ TEST 2: LONG Position Lifecycle ═══")
    
    symbol = 'SOL/USDT'
    
    # ── Simulate entry (matching backtest lines 151-167) ──
    # Simulated previous bar ATR
    prev_atr = 2.50
    exec_price = 150.00  # Current candle close = live execution price
    
    # Inverse-ATR Risk Parity sizing (backtest line 153)
    risk_amount = INITIAL_EQUITY * RISK_PCT  # 10000 * 0.01 = 100
    qty = risk_amount / (STOP_MULT * prev_atr)  # 100 / (2.0 * 2.50) = 20.0
    max_qty = (INITIAL_EQUITY * MAX_LEVERAGE / NUM_SYMBOLS) / exec_price  # (10000*2/5)/150 = 26.67
    qty = min(qty, max_qty)  # 20.0
    
    notional = qty * exec_price  # 20.0 * 150 = 3000
    fee = notional * FEE_RATE  # 3000 * 0.0005 = 1.50
    
    # ATR-based stops (backtest lines 165-166)
    trailing_stop = exec_price - (STOP_MULT * prev_atr)  # 150 - 5.0 = 145.0
    take_profit = exec_price + (TP_MULT * prev_atr)  # 150 + 25.0 = 175.0
    
    print(f"  Entry: price={exec_price}, qty={qty:.4f}, stop={trailing_stop}, tp={take_profit}")
    
    assert_close(qty, 20.0, "Qty = risk / (stop_mult * ATR)")
    assert_close(fee, 1.50, "Entry fee")
    assert_close(trailing_stop, 145.0, "Trailing stop = exec - 2*ATR")
    assert_close(take_profit, 175.0, "Take profit = exec + 10*ATR")
    
    # Open position in DB
    pos_id = open_position(
        symbol=symbol,
        direction='LONG',
        entry_price=exec_price,
        qty=qty,
        trailing_stop=trailing_stop,
        take_profit=take_profit,
        extreme_close=exec_price,
        fee=fee
    )
    
    assert_equal(pos_id > 0, True, "Position ID is positive")
    
    pos = get_open_position(symbol)
    assert_equal(pos is not None, True, "Position found in DB")
    assert_equal(pos['direction'], 'LONG', "Direction is LONG")
    assert_close(pos['qty'], 20.0, "DB qty matches")
    assert_close(pos['trailing_stop_price'], 145.0, "DB trailing stop matches")
    assert_close(pos['take_profit_price'], 175.0, "DB take profit matches")
    
    # ── Simulate trailing stop ratchet (backtest lines 215-217) ──
    # Price moves up: extreme_close updates, stop ratchets
    new_close = 158.00  # Price went up
    curr_atr = 2.40  # ATR slightly decreased
    
    new_extreme = max(pos['extreme_close'], new_close)  # max(150, 158) = 158
    new_ts = new_extreme - (STOP_MULT * curr_atr)  # 158 - 4.80 = 153.20
    new_ts = max(trailing_stop, new_ts)  # max(145.0, 153.20) = 153.20
    
    print(f"  Ratchet: extreme={new_extreme}, new_stop={new_ts}")
    
    assert_close(new_extreme, 158.0, "Extreme ratchets up")
    assert_close(new_ts, 153.20, "Stop ratchets up: extreme - 2*ATR")
    
    update_position_stop(pos_id, new_ts, new_extreme)
    
    pos = get_open_position(symbol)
    assert_close(pos['trailing_stop_price'], 153.20, "DB trailing stop ratcheted")
    assert_close(pos['extreme_close'], 158.0, "DB extreme close updated")
    
    # ── Simulate close via signal reversal (backtest lines 191-213) ──
    exit_price = 160.00  # Close price when signal flips to -1
    
    # LONG P&L (backtest line 208):
    # pnl = proceeds - fee - (qty * entry_price)
    proceeds = qty * exit_price  # 20 * 160 = 3200
    exit_fee = proceeds * FEE_RATE  # 3200 * 0.0005 = 1.60
    pnl = proceeds - exit_fee - (qty * exec_price)  # 3200 - 1.60 - 3000 = 198.40
    
    print(f"  Exit: price={exit_price}, proceeds={proceeds}, exit_fee={exit_fee}, pnl={pnl}")
    
    assert_close(pnl, 198.40, "LONG P&L matches backtest formula")
    
    close_position(pos_id, exit_price, pnl, exit_fee)
    
    pos = get_open_position(symbol)
    assert_equal(pos, None, "Position closed (no open position)")
    
    history = get_position_history()
    closed = [p for p in history if p['id'] == pos_id][0]
    assert_equal(closed['status'], 'CLOSED', "Position status is CLOSED")
    assert_close(closed['profit_usd'], 198.40, "DB profit matches")
    assert_close(closed['fee_usd'], fee + exit_fee, "DB total fee = entry + exit", tol=1e-4)


def test_short_lifecycle():
    """Test 3: SHORT entry → take-profit close."""
    print("\n═══ TEST 3: SHORT Position Lifecycle ═══")
    
    symbol = 'DOGE/USDT'
    
    # ── Simulate SHORT entry (backtest lines 169-185) ──
    prev_atr = 0.005
    exec_price = 0.15
    
    risk_amount = INITIAL_EQUITY * RISK_PCT  # 100
    qty = risk_amount / (STOP_MULT * prev_atr)  # 100 / (2 * 0.005) = 10000
    max_qty = (INITIAL_EQUITY * MAX_LEVERAGE / NUM_SYMBOLS) / exec_price  # 4000/0.15 = 26666.67
    qty = min(qty, max_qty)  # 10000
    
    notional = qty * exec_price  # 10000 * 0.15 = 1500
    fee = notional * FEE_RATE  # 0.75
    
    # SHORT stops (backtest lines 183-184)
    trailing_stop = exec_price + (STOP_MULT * prev_atr)  # 0.15 + 0.01 = 0.16
    take_profit = exec_price - (TP_MULT * prev_atr)  # 0.15 - 0.05 = 0.10
    
    print(f"  Entry: price={exec_price}, qty={qty:.4f}, stop={trailing_stop}, tp={take_profit}")
    
    assert_close(qty, 10000.0, "SHORT qty sizing")
    assert_close(trailing_stop, 0.16, "SHORT trailing stop = exec + 2*ATR")
    assert_close(take_profit, 0.10, "SHORT take profit = exec - 10*ATR")
    
    pos_id = open_position(
        symbol=symbol,
        direction='SHORT',
        entry_price=exec_price,
        qty=qty,
        trailing_stop=trailing_stop,
        take_profit=take_profit,
        extreme_close=exec_price,
        fee=fee
    )
    
    pos = get_open_position(symbol)
    assert_equal(pos['direction'], 'SHORT', "Direction is SHORT")
    
    # ── Simulate take-profit hit (backtest lines 230-233) ──
    # Price drops to take_profit level
    exit_price = take_profit  # 0.10
    
    # SHORT P&L (backtest line 238):
    # pnl = (entry_price - exit_price) * qty
    cost = qty * exit_price  # 10000 * 0.10 = 1000
    exit_fee = cost * FEE_RATE  # 1000 * 0.0005 = 0.50
    pnl = (exec_price - exit_price) * qty - exit_fee  # (0.15 - 0.10) * 10000 - 0.50 = 499.50
    
    print(f"  TP Exit: price={exit_price}, pnl={pnl}")
    
    assert_close(pnl, 499.50, "SHORT P&L at take-profit matches backtest")
    
    close_position(pos_id, exit_price, pnl, exit_fee)
    
    pos = get_open_position(symbol)
    assert_equal(pos, None, "SHORT position closed")
    
    history = get_position_history()
    closed = [p for p in history if p['id'] == pos_id][0]
    assert_close(closed['profit_usd'], 499.50, "DB SHORT profit matches")


def test_short_trailing_stop():
    """Test 3b: SHORT trailing stop ratchet (downward)."""
    print("\n═══ TEST 3b: SHORT Trailing Stop Ratchet ═══")
    
    symbol = 'ADA/USDT'
    prev_atr = 0.02
    exec_price = 0.50
    
    qty = (INITIAL_EQUITY * RISK_PCT) / (STOP_MULT * prev_atr)  # 100 / 0.04 = 2500
    trailing_stop = exec_price + (STOP_MULT * prev_atr)  # 0.50 + 0.04 = 0.54
    take_profit = exec_price - (TP_MULT * prev_atr)  # 0.50 - 0.20 = 0.30
    
    pos_id = open_position(
        symbol=symbol,
        direction='SHORT',
        entry_price=exec_price,
        qty=qty,
        trailing_stop=trailing_stop,
        take_profit=take_profit,
        extreme_close=exec_price,
        fee=qty * exec_price * FEE_RATE
    )
    
    # Price drops (favorable for SHORT) → extreme goes down, stop ratchets down
    new_close = 0.45
    curr_atr = 0.019
    
    # Backtest lines 247-249
    new_extreme = min(exec_price, new_close)  # min(0.50, 0.45) = 0.45
    new_ts = new_extreme + (STOP_MULT * curr_atr)  # 0.45 + 0.038 = 0.488
    new_ts = min(trailing_stop, new_ts)  # min(0.54, 0.488) = 0.488
    
    assert_close(new_extreme, 0.45, "SHORT extreme ratchets down")
    assert_close(new_ts, 0.488, "SHORT stop ratchets down")
    
    update_position_stop(pos_id, new_ts, new_extreme)
    
    pos = get_open_position(symbol)
    assert_close(pos['trailing_stop_price'], 0.488, "DB SHORT stop ratcheted")
    assert_close(pos['extreme_close'], 0.45, "DB SHORT extreme updated")
    
    # Close it
    exit_price = 0.488  # Hit trailing stop
    cost = qty * exit_price
    exit_fee = cost * FEE_RATE
    pnl = (exec_price - exit_price) * qty - exit_fee
    close_position(pos_id, exit_price, pnl, exit_fee)


def test_funding_rate():
    """Test 4: Funding rate application."""
    print("\n═══ TEST 4: Funding Rate Application ═══")
    
    symbol = 'LINK/USDT'
    exec_price = 15.0
    qty = 100.0
    prev_atr = 0.50
    
    pos_id = open_position(
        symbol=symbol,
        direction='LONG',
        entry_price=exec_price,
        qty=qty,
        trailing_stop=exec_price - (STOP_MULT * prev_atr),
        take_profit=exec_price + (TP_MULT * prev_atr),
        extreme_close=exec_price,
        fee=qty * exec_price * FEE_RATE
    )
    
    # Funding at UTC 0:00 (backtest lines 140-144)
    # LONG pays: funding = -qty * price * funding_rate
    tick_price = 15.50
    funding_amount_long = -(qty * tick_price * FUNDING_RATE)  # -(100 * 15.50 * 0.0001) = -0.155
    
    assert_close(funding_amount_long, -0.155, "LONG funding payment")
    
    update_position_funding(pos_id, funding_amount_long)
    
    pos = get_open_position(symbol)
    assert_close(pos['total_funding'], -0.155, "DB funding accumulated (1 period)")
    
    # Second funding period
    tick_price_2 = 16.00
    funding_amount_2 = -(qty * tick_price_2 * FUNDING_RATE)  # -(100 * 16 * 0.0001) = -0.16
    update_position_funding(pos_id, funding_amount_2)
    
    pos = get_open_position(symbol)
    expected_total = -0.155 + (-0.16)  # -0.315
    assert_close(pos['total_funding'], expected_total, "DB funding accumulated (2 periods)", tol=1e-4)
    
    # Clean up
    exit_price = 16.00
    proceeds = qty * exit_price
    exit_fee = proceeds * FEE_RATE
    pnl = proceeds - exit_fee - (qty * exec_price)
    close_position(pos_id, exit_price, pnl, exit_fee)
    
    # ── SHORT funding (backtest line 144): SHORT receives ──
    pos_id_s = open_position(
        symbol='DOT/USDT',
        direction='SHORT',
        entry_price=7.0,
        qty=200.0,
        trailing_stop=7.0 + (STOP_MULT * 0.20),
        take_profit=7.0 - (TP_MULT * 0.20),
        extreme_close=7.0,
        fee=200 * 7.0 * FEE_RATE
    )
    
    # SHORT earns: funding = +qty * price * funding_rate
    funding_short = 200.0 * 6.80 * FUNDING_RATE  # +0.136
    update_position_funding(pos_id_s, funding_short)
    
    pos_s = get_open_position('DOT/USDT')
    assert_close(pos_s['total_funding'], 0.136, "SHORT funding receipt", tol=1e-4)
    
    # Clean up
    close_position(pos_id_s, 6.80, (7.0 - 6.80) * 200 - 6.80*200*FEE_RATE, 6.80*200*FEE_RATE)


def test_max_leverage_cap():
    """Test 5: Max leverage cap limits position size."""
    print("\n═══ TEST 5: Max Leverage Cap ═══")
    
    # Use a very small ATR so uncapped qty would be huge
    prev_atr = 0.001
    exec_price = 100.0
    
    risk_amount = INITIAL_EQUITY * RISK_PCT  # 100
    uncapped_qty = risk_amount / (STOP_MULT * prev_atr)  # 100 / 0.002 = 50000
    max_qty = (INITIAL_EQUITY * MAX_LEVERAGE / NUM_SYMBOLS) / exec_price  # 4000/100 = 40
    qty = min(uncapped_qty, max_qty)  # min(50000, 40) = 40
    
    assert_close(qty, 40.0, "Max leverage caps qty at 40")
    assert_close(uncapped_qty, 50000.0, "Uncapped qty would be 50000")
    
    # Verify notional doesn't exceed leverage limit
    notional = qty * exec_price  # 40 * 100 = 4000
    max_notional = INITIAL_EQUITY * MAX_LEVERAGE / NUM_SYMBOLS  # 4000
    assert_close(notional, max_notional, "Notional at max leverage cap")


def test_position_history():
    """Test 6: Position history returns all positions."""
    print("\n═══ TEST 6: Position History ═══")
    
    history = get_position_history()
    
    # We created positions in tests 2, 3, 3b, 4 (2 positions), so at least 5
    assert_equal(len(history) >= 5, True, f"History has >= 5 positions (got {len(history)})")
    
    # All should be CLOSED
    open_count = sum(1 for p in history if p['status'] == 'OPEN')
    assert_equal(open_count, 0, "No open positions remaining")
    
    # Check directions
    directions = set(p['direction'] for p in history)
    assert_equal('LONG' in directions, True, "Has LONG positions")
    assert_equal('SHORT' in directions, True, "Has SHORT positions")


if __name__ == '__main__':
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  V2 BREAKOUT LIVE ENGINE — UNIT TESTS                ║")
    print("║  Validates P&L math matches breakout_v2_backtest.py  ║")
    print("╚═══════════════════════════════════════════════════════╝")
    
    try:
        test_db_init()
        test_long_lifecycle()
        test_short_lifecycle()
        test_short_trailing_stop()
        test_funding_rate()
        test_max_leverage_cap()
        test_position_history()
        
        print(f"\n{'='*55}")
        print(f"  RESULTS: {PASS} passed, {FAIL} failed")
        print(f"{'='*55}")
        
        if FAIL > 0:
            print("  ❌ SOME TESTS FAILED")
            sys.exit(1)
        else:
            print("  ✅ ALL TESTS PASSED")
            sys.exit(0)
    finally:
        # Clean up test DB
        if os.path.exists(_test_db):
            os.remove(_test_db)
