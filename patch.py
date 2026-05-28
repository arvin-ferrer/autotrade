import re

with open("web/app.py", "r") as f:
    content = f.read()

# Replace get_portfolio_metrics
old_get_metrics = """def get_portfolio_metrics(fx_rate: float, btc_price_usd: float) -> Dict[str, Any]:
    \"\"\"Calculate key performance indicators from the database and live price\"\"\"
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch cash & holdings
    cursor.execute("SELECT cash_php, btc_holdings FROM portfolio WHERE id = 1")
    portfolio_row = cursor.fetchone()
    if not portfolio_row:
        conn.close()
        return {}
        
    cash_php = float(portfolio_row['cash_php'])
    btc_holdings = float(portfolio_row['btc_holdings'])
    
    # 2. Fetch trade statistics
    cursor.execute("SELECT * FROM trades")
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    total_trades = len(trades)
    closed_trades = [t for t in trades if t['status'] == 'CLOSED']
    open_trades = [t for t in trades if t['status'] == 'OPEN']
    
    win_count = sum(1 for t in closed_trades if float(t['profit_usd'] or 0.0) > 0.0)
    win_rate = (win_count / len(closed_trades) * 100.0) if closed_trades else 0.0
    
    # 3. Calculate portfolio estimations
    btc_value_usd = btc_holdings * btc_price_usd
    btc_value_php = btc_value_usd * fx_rate
    total_value_php = cash_php + btc_value_php
    total_value_usd = total_value_php / fx_rate
    
    # Initial capital configuration fallback
    # Attempt to derive initial PHP cash by looking at the first open trade or portfolio state
    # By default, initial cash is 500,000 PHP.
    initial_cash_php = 500000.0
    if trades:
        # If the first trade closed with cash, we reconstruct the initial cash
        # Or we can just use 500,000 PHP as a standard reference
        pass
        
    total_profit_php = total_value_php - initial_cash_php
    total_profit_pct = (total_profit_php / initial_cash_php) * 100.0
    
    return {
        'cash_php': cash_php,
        'btc_holdings': btc_holdings,
        'btc_price_usd': btc_price_usd,
        'btc_price_php': btc_price_usd * fx_rate,
        'btc_value_php': btc_value_php,
        'total_value_php': total_value_php,
        'total_value_usd': total_value_usd,
        'total_profit_php': total_profit_php,
        'total_profit_pct': total_profit_pct,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'open_position': btc_holdings > 0.0,
        'active_trade': open_trades[0] if open_trades else None
    }"""

new_get_metrics = """def get_portfolio_metrics(fx_rate: float) -> Dict[str, Any]:
    \"\"\"Calculate key performance indicators from the database and live prices\"\"\"
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
    }"""

content = content.replace(old_get_metrics, new_get_metrics)

# Replace api_metrics
old_api_metrics = """@app.get("/api/metrics")
async def api_metrics():
    \"\"\"HTTP API endpoint for metrics\"\"\"
    try:
        ticker = exchange.fetch_ticker('BTC/USDT')
        btc_price_usd = float(ticker['last'])
    except Exception:
        btc_price_usd = 70000.0 # Fallback
        
    fx_rate = fetch_live_fx_rate()
    return get_portfolio_metrics(fx_rate, btc_price_usd)"""

new_api_metrics = """@app.get("/api/metrics")
async def api_metrics():
    \"\"\"HTTP API endpoint for metrics\"\"\"
    fx_rate = await asyncio.to_thread(fetch_live_fx_rate)
    return await asyncio.to_thread(get_portfolio_metrics, fx_rate)"""

content = content.replace(old_api_metrics, new_api_metrics)

# Replace websocket loop
old_ws = """            # 1. Fetch live exchange pricing
            try:
                # Run fetch_ticker in executors to avoid blocking loop
                ticker = await asyncio.to_thread(exchange.fetch_ticker, 'BTC/USDT')
                btc_price_usd = float(ticker['last'])
            except Exception as e:
                print(f"[WS Error] Fetching price failed: {e}")
                btc_price_usd = 70000.0 # Standard fallback
                
            # 2. Fetch live FX exchange rate
            fx_rate = await asyncio.to_thread(fetch_live_fx_rate)
            
            # 3. Pull SQL metrics
            metrics = get_portfolio_metrics(fx_rate, btc_price_usd)"""

new_ws = """            # 1. Fetch live FX exchange rate
            fx_rate = await asyncio.to_thread(fetch_live_fx_rate)
            
            # 2. Pull SQL metrics dynamically (also fetches ticker prices)
            metrics = await asyncio.to_thread(get_portfolio_metrics, fx_rate)"""

content = content.replace(old_ws, new_ws)

with open("web/app.py", "w") as f:
    f.write(content)
print("Done patching app.py")
