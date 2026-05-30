import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional
import json

DB_FILE = "live_trading.db"

def get_pht_now() -> str:
    """Return current time formatted in Philippines Time (UTC+8)"""
    pht = datetime.now(timezone(timedelta(hours=8)))
    return pht.strftime('%Y-%m-%d %H:%M:%S PHT')

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(initial_cash_php: float = 500000.0) -> None:
    """
    Initialize the SQLite database with portfolio and trade tables.
    If the portfolio table is empty, initializes it with the default PHP balance.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    
    # Check if portfolio has btc_holdings
    cursor.execute("PRAGMA table_info(portfolio)")
    columns = [col['name'] for col in cursor.fetchall()]
    if 'btc_holdings' in columns:
        cursor.execute("DROP TABLE portfolio")
        
    # Create portfolio state table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        cash_php REAL NOT NULL,
        holdings_json TEXT NOT NULL DEFAULT '{}',
        last_updated TEXT NOT NULL
    )
    """)
    
    # Check if trades has stop_price_usd
    cursor.execute("PRAGMA table_info(trades)")
    trade_columns = [col['name'] for col in cursor.fetchall()]
    if trade_columns and 'stop_price_usd' not in trade_columns:
        cursor.execute("DROP TABLE trades")
        
    # Create trades table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        entry_time TEXT NOT NULL,
        exit_time TEXT,
        entry_price_usd REAL NOT NULL,
        entry_price_php REAL NOT NULL,
        exit_price_usd REAL,
        exit_price_php REAL,
        size REAL NOT NULL,
        fee_usd REAL NOT NULL,
        fee_php REAL NOT NULL,
        profit_usd REAL,
        profit_php REAL,
        stop_price_usd REAL,
        highest_price_usd REAL,
        status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED'))
    )
    """)
    
    conn.commit()
    
    # Initialize portfolio check
    cursor.execute("SELECT COUNT(*) FROM portfolio")
    if cursor.fetchone()[0] == 0:
        now_str = get_pht_now()
        cursor.execute(
            "INSERT INTO portfolio (id, cash_php, holdings_json, last_updated) VALUES (1, ?, '{}', ?)",
            (initial_cash_php, now_str)
        )
        conn.commit()
        print(f"[DB] Initialized paper portfolio with ₱{initial_cash_php:,.2f} PHP at {now_str}")
        
    conn.close()

def get_portfolio() -> Tuple[float, dict]:
    """
    Returns the current portfolio state: (cash_php, holdings_dict).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT cash_php, holdings_json FROM portfolio WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return float(row['cash_php']), json.loads(row['holdings_json'])

def update_portfolio(cash_php: float, holdings: dict) -> None:
    """
    Update cash and holdings in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = get_pht_now()
    cursor.execute(
        "UPDATE portfolio SET cash_php = ?, holdings_json = ?, last_updated = ? WHERE id = 1",
        (cash_php, json.dumps(holdings), now_str)
    )
    conn.commit()
    conn.close()

def get_open_trade(symbol: str = None) -> Optional[Dict[str, Any]]:
    """
    Get the active open trade if one exists (filtered by symbol if provided), otherwise returns None.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    if symbol:
        cursor.execute("SELECT * FROM trades WHERE status = 'OPEN' AND symbol = ?", (symbol,))
    else:
        cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def open_trade(
    symbol: str, 
    entry_price_usd: float, 
    entry_price_php: float, 
    size: float, 
    fee_usd: float, 
    fee_php: float,
    stop_price_usd: float,
    highest_price_usd: float
) -> int:
    """
    Inserts a new open trade into the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = get_pht_now()
    cursor.execute(
        """
        INSERT INTO trades (
            symbol, entry_time, entry_price_usd, entry_price_php, 
            size, fee_usd, fee_php, stop_price_usd, highest_price_usd, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
        """,
        (symbol, now_str, entry_price_usd, entry_price_php, size, fee_usd, fee_php, stop_price_usd, highest_price_usd)
    )
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trade_id

def close_trade(
    trade_id: int, 
    exit_price_usd: float, 
    exit_price_php: float, 
    fee_usd: float, 
    fee_php: float,
    profit_usd: float, 
    profit_php: float
) -> None:
    """
    Closes an active trade, recording the exit data and profits.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = get_pht_now()
    cursor.execute(
        """
        UPDATE trades 
        SET exit_time = ?, exit_price_usd = ?, exit_price_php = ?, 
            fee_usd = fee_usd + ?, fee_php = fee_php + ?,
            profit_usd = ?, profit_php = ?, status = 'CLOSED'
        WHERE id = ?
        """,
        (now_str, exit_price_usd, exit_price_php, fee_usd, fee_php, profit_usd, profit_php, trade_id)
    )
    conn.commit()
    conn.close()

def update_trade_stop(trade_id: int, new_stop: float, new_highest: float) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE trades SET stop_price_usd = ?, highest_price_usd = ? WHERE id = ?",
        (new_stop, new_highest, trade_id)
    )
    conn.commit()
    conn.close()

def get_trade_history() -> List[Dict[str, Any]]:
    """
    Returns a list of all trades (both open and closed) ordered chronologically.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
