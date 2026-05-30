import os
import sqlite3
import asyncio
import json
import urllib.request
from typing import Dict, Any, List
import ccxt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# Create directories if they do not exist
os.makedirs("web/templates", exist_ok=True)
os.makedirs("web/static", exist_ok=True)

app = FastAPI(title="Bitcoin Algo Trader Dashboard")

# Mount static and templates
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

DB_FILE = "live_trading.db"
FALLBACK_FX_RATE = 58.5
exchange = ccxt.binance({'enableRateLimit': True})

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_live_fx_rate() -> float:
    """Fetch USD/PHP exchange rate from Frankfurter API"""
    url = "https://api.frankfurter.app/latest?from=USD&to=PHP"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            return float(data['rates']['PHP'])
    except Exception:
        # Fallback if API fails
        return FALLBACK_FX_RATE

def get_portfolio_metrics(fx_rate: float) -> Dict[str, Any]:
    """Calculate key performance indicators from the database and live prices"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch cash & holdings
    try:
        cursor.execute("SELECT cash_php, holdings_json FROM portfolio WHERE id = 1")
    except sqlite3.OperationalError:
        cursor.execute("SELECT cash_php, btc_holdings FROM portfolio WHERE id = 1")
    
    portfolio_row = cursor.fetchone()
    if not portfolio_row:
        conn.close()
        return {}
        
    cash_php = float(portfolio_row['cash_php'])
    
    holdings = {}
    if 'holdings_json' in portfolio_row.keys():
        holdings_json = portfolio_row['holdings_json']
        try:
            holdings = json.loads(holdings_json) if holdings_json else {}
        except Exception:
            holdings = {}
    elif 'btc_holdings' in portfolio_row.keys():
        btc_h = float(portfolio_row['btc_holdings'])
        if btc_h > 0:
            holdings = {'BTC/USDT': btc_h}
            
    # 2. Fetch trade statistics
    cursor.execute("SELECT * FROM trades")
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    total_trades = len(trades)
    closed_trades = [t for t in trades if t['status'] == 'CLOSED']
    open_trades = [t for t in trades if t['status'] == 'OPEN']
    
    win_count = sum(1 for t in closed_trades if float(t['profit_usd'] or 0.0) > 0.0)
    win_rate = (win_count / len(closed_trades) * 100.0) if closed_trades else 0.0
    
    # 3. Calculate portfolio estimations dynamically
    total_assets_usd = 0.0
    assets_info = []
    
    for symbol, amount in holdings.items():
        if amount > 0:
            try:
                ticker = exchange.fetch_ticker(symbol)
                price_usd = float(ticker['last'])
            except Exception:
                price_usd = 70000.0 if 'BTC' in symbol else 0.0
                
            value_usd = price_usd * amount
            value_php = value_usd * fx_rate
            total_assets_usd += value_usd
            
            assets_info.append({
                'symbol': symbol,
                'amount': amount,
                'price_usd': price_usd,
                'price_php': price_usd * fx_rate,
                'value_usd': value_usd,
                'value_php': value_php
            })
            
    total_assets_php = total_assets_usd * fx_rate
    total_value_php = cash_php + total_assets_php
    total_value_usd = total_value_php / fx_rate
    
    initial_cash_php = 500000.0
    
    total_profit_php = total_value_php - initial_cash_php
    total_profit_pct = (total_profit_php / initial_cash_php) * 100.0
    
    return {
        'cash_php': cash_php,
        'assets': assets_info,
        'total_assets_php': total_assets_php,
        'total_value_php': total_value_php,
        'total_value_usd': total_value_usd,
        'total_profit_php': total_profit_php,
        'total_profit_pct': total_profit_pct,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'open_position': len(assets_info) > 0,
        'active_trade': open_trades[0] if open_trades else None
    }

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serve main dashboard page"""
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/metrics")
async def api_metrics():
    """HTTP API endpoint for metrics"""
    fx_rate = await asyncio.to_thread(fetch_live_fx_rate)
    return await asyncio.to_thread(get_portfolio_metrics, fx_rate)

@app.get("/api/trades")
async def api_trades():
    """HTTP API endpoint for full trade log"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades ORDER BY id DESC")
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return trades

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket stream for real-time tick updates"""
    await websocket.accept()
    print("[WebSocket] Client connected")
    try:
        while True:
            # 1. Fetch live FX exchange rate
            fx_rate = await asyncio.to_thread(fetch_live_fx_rate)
            
            # 2. Pull SQL metrics dynamically (also fetches ticker prices)
            metrics = await asyncio.to_thread(get_portfolio_metrics, fx_rate)
            
            # 4. Pull SQLite trade list to build equity curves
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT exit_time, profit_php FROM trades WHERE status = 'CLOSED' ORDER BY id ASC")
            closed_trades = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            # Reconstruct running equity points
            running_balance = 500000.0
            equity_curve_data = [{'timestamp': 'Initial', 'balance': running_balance}]
            for idx, t in enumerate(closed_trades, 1):
                running_balance += float(t['profit_php'] or 0.0)
                equity_curve_data.append({
                    'timestamp': t['exit_time'].split(' ')[0],  # Get only the Date YYYY-MM-DD
                    'balance': running_balance
                })
                
            payload = {
                'metrics': metrics,
                'equity_curve': equity_curve_data
            }
            
            await websocket.send_json(payload)
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        print("[WebSocket] Client disconnected")
    except Exception as e:
        print(f"[WebSocket Loop Error] {e}")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("web.app:app", host="0.0.0.0", port=port)
