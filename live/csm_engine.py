import asyncio
import json
import websockets
import pandas as pd
import numpy as np
from typing import Optional, List
from live.db import get_pht_now, get_portfolio, update_portfolio, get_open_trade, open_trade, close_trade
from data.loader import get_ohlcv
from live.executor import send_discord_alert
import threading

portfolio_lock = threading.Lock()

def process_daily_kama(
    symbols: List[str],
    df_buffers: dict,
    fee_rate: float,
    php_usd_rate: float,
    discord_webhook_url: Optional[str]
):
    """
    Executed exactly once per day at 00:00:00 UTC (when daily candles close).
    Calculates KAMA, ER, and the 100-Day Macro Gate.
    Executes liquidations and entries.
    """
    with portfolio_lock:
        cash_php, holdings = get_portfolio()
        
        # Build cross-sectional dataframes
        close_prices = pd.DataFrame({sym: df_buffers[sym]['Close'] for sym in symbols}).dropna(how='all')
        if close_prices.empty: return
        
        # 1. MACRO GATE MATH
        btc_close = close_prices['BTC/USDT']
        btc_sma = btc_close.rolling(100).mean()
        
        current_gate = False
        for i in range(len(btc_close)):
            c_val = btc_close.iloc[i]
            s_val = btc_sma.iloc[i]
            if pd.isna(s_val): continue
            if not current_gate and c_val > s_val * 1.02: current_gate = True
            elif current_gate and c_val < s_val * 0.98: current_gate = False
            
        is_macro_open = current_gate
        print(f"[{get_pht_now()}] Daily Macro Gate Status: {'OPEN' if is_macro_open else 'CLOSED'}")
        
        # 2. Calculate KAMA and ER for all symbols
        indicators = {}
        for sym in symbols:
            close = close_prices[sym]
            n = 10
            fastest_sc = 2 / 3
            slowest_sc = 2 / 31
            
            change = close.diff(n).abs()
            volatility = close.diff(1).abs().rolling(n).sum()
            er = change / volatility
            sc = (er * (fastest_sc - slowest_sc) + slowest_sc) ** 2
            
            kama = np.zeros_like(close.values)
            kama[:] = np.nan
            
            close_arr = close.values
            sc_arr = sc.values
            
            first_valid = sc.first_valid_index()
            if first_valid is not None:
                idx = close.index.get_loc(first_valid)
                kama[idx-1] = close_arr[idx-1]
                for i in range(idx, len(close_arr)):
                    kama[i] = kama[i-1] + sc_arr[i] * (close_arr[i] - kama[i-1])
            
            indicators[sym] = {
                'kama': kama[-1],
                'er': er.iloc[-1],
                'close': close.iloc[-1]
            }

        # 3. Step 1: Liquidations
        for sym in symbols:
            open_t = get_open_trade(sym)
            asset_holding = holdings.get(sym, 0.0)
            if open_t is not None and asset_holding > 0.0:
                ind = indicators[sym]
                
                # Exit if close crosses below KAMA, OR if Macro Gate closes
                exit_signal = (ind['close'] < ind['kama']) or (not is_macro_open)
                
                if exit_signal:
                    sell_price_usd = ind['close']
                    sell_price_php = sell_price_usd * php_usd_rate
                    sell_value_usd = asset_holding * sell_price_usd
                    fee_usd = sell_value_usd * fee_rate
                    net_cash_usd = sell_value_usd - fee_usd
                    net_cash_php = net_cash_usd * php_usd_rate
                    
                    entry_cost_usd = open_t['size'] * open_t['entry_price_usd']
                    profit_usd = net_cash_usd - entry_cost_usd
                    profit_php = profit_usd * php_usd_rate
                    
                    holdings[sym] = 0.0
                    cash_php += net_cash_php
                    close_trade(
                        trade_id=open_t['id'], exit_price_usd=sell_price_usd, exit_price_php=sell_price_php,
                        fee_usd=fee_usd, fee_php=fee_usd * php_usd_rate, profit_usd=profit_usd, profit_php=profit_php
                    )
                    reason = "MACRO GATE CLOSED" if not is_macro_open else "TREND BROKEN (Close < KAMA)"
                    print(f"[{get_pht_now()}] 🛑 SELL SIGNAL ({sym}): {reason}")
                    send_discord_alert(discord_webhook_url, f"🛑 SELL {sym}", reason, 15158332, [])
        
        # Determine Current Equity
        current_equity_php = cash_php
        for sym in symbols:
            if holdings.get(sym, 0.0) > 0.0:
                current_equity_php += holdings[sym] * indicators[sym]['close'] * php_usd_rate
                
        # 4. Step 2: Entries
        buy_candidates = []
        if is_macro_open:
            for sym in symbols:
                if holdings.get(sym, 0.0) == 0.0:
                    ind = indicators[sym]
                    if pd.isna(ind['kama']) or pd.isna(ind['er']): continue
                    
                    # Entry: Close > KAMA and ER > 0.30 (Trending)
                    if ind['close'] > ind['kama'] and ind['er'] > 0.30:
                        buy_candidates.append(sym)
                        
        max_positions = 5
        current_positions = sum(1 for sym in symbols if holdings.get(sym, 0.0) > 0)
        available_slots = max_positions - current_positions
        
        if buy_candidates and available_slots > 0:
            # Sort by Efficiency Ratio (smoothest trends first)
            buy_candidates.sort(key=lambda s: indicators[s]['er'], reverse=True)
            to_buy = buy_candidates[:available_slots]
            
            target_allocation_php = current_equity_php / max_positions
            allocation_per_asset_php = min(cash_php, target_allocation_php) * 0.99
            allocation_per_asset_usd = allocation_per_asset_php / php_usd_rate
            
            for sym in to_buy:
                buy_price_usd = indicators[sym]['close']
                buy_size = (allocation_per_asset_usd * (1 - fee_rate)) / buy_price_usd
                fee_usd = allocation_per_asset_usd * fee_rate
                
                if allocation_per_asset_usd > 10.0:
                    holdings[sym] = buy_size
                    cash_php -= allocation_per_asset_php
                    
                    open_trade(
                        symbol=sym, entry_price_usd=buy_price_usd, entry_price_php=buy_price_usd*php_usd_rate,
                        size=buy_size, fee_usd=fee_usd, fee_php=fee_usd*php_usd_rate,
                        stop_price_usd=0.0, highest_price_usd=buy_price_usd # No intraday stop tracking needed for KAMA
                    )
                    
                    print(f"[{get_pht_now()}] 🛒 BUY SIGNAL ({sym}): Close > KAMA and ER={indicators[sym]['er']:.2f}")
                    send_discord_alert(discord_webhook_url, f"🛒 BUY {sym}", f"Trend confirmed.", 3066993, [])

        update_portfolio(cash_php=cash_php, holdings=holdings)

async def connect_csm_websocket(symbols: List[str], fee_rate: float, php_usd_rate: float, discord_webhook_url: Optional[str]):
    ws_streams = [f"{sym.replace('/', '').lower()}@kline_1d" for sym in symbols]
    url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(ws_streams)}"
    
    print(f"[{get_pht_now()}] Fetching 150-day bootstrap buffers...")
    df_buffers = {}
    now = pd.Timestamp.now(tz='UTC')
    start_str = (now - pd.Timedelta(days=150)).strftime('%Y-%m-%d %H:%M:%S')
    
    for sym in symbols:
        df_buffers[sym] = get_ohlcv(sym, '1d', start_date=start_str)
        
    stream_to_symbol = {f"{sym.replace('/', '').lower()}@kline_1d": sym for sym in symbols}
    closed_today = set()

    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as websocket:
        print(f"[{get_pht_now()}] Connected to Live KAMA Engine!")
        
        # Send Startup Notification to Discord
        await asyncio.to_thread(
            send_discord_alert,
            webhook_url=discord_webhook_url,
            title="🟢 SYSTEM ONLINE: KAMA ENGINE",
            description=f"Connected to live WebSocket streams for {len(symbols)} assets. Awaiting daily candle close at 00:00 UTC.",
            color=3066993, # Green
            fields=[]
        )
        
        async for message in websocket:
            event = json.loads(message)
            if 'data' not in event: continue
            
            data = event['data']['k']
            symbol_k = stream_to_symbol.get(event['stream'])
            
            # Periodic Price Watch (Print BTC price every 5 minutes)
            if symbol_k == 'BTC/USDT':
                import time
                current_time = time.time()
                # Initialize last_print_time attribute on the function if it doesn't exist
                if not hasattr(connect_csm_websocket, "last_print_time"):
                    connect_csm_websocket.last_print_time = 0
                    
                if current_time - connect_csm_websocket.last_print_time > 300: # 300 seconds = 5 minutes
                    print(f"[{get_pht_now()}] 👁️ Price Watch | {symbol_k}: ${float(data['c']):,.2f} | Awaiting Daily Close...")
                    connect_csm_websocket.last_print_time = current_time
            
            # Accumulate Daily Closes
            if data['x']: # is_closed
                dt = pd.to_datetime(data['t'], unit='ms', utc=True)
                new_row = pd.DataFrame([{
                    'Open': float(data['o']), 'High': float(data['h']), 'Low': float(data['l']),
                    'Close': float(data['c']), 'Volume': float(data['v'])
                }], index=[dt])
                
                df_buf = df_buffers[symbol_k]
                df_buf = pd.concat([df_buf, new_row])
                df_buf = df_buf[~df_buf.index.duplicated(keep='last')].tail(200)
                df_buffers[symbol_k] = df_buf
                
                closed_today.add(symbol_k)
                print(f"[{get_pht_now()}] 1d Candle Closed for {symbol_k}")
                
                # When all symbols have closed their daily candle
                if len(closed_today) == len(symbols):
                    print(f"[{get_pht_now()}] All daily candles closed. Processing KAMA Engine...")
                    await asyncio.to_thread(
                        process_daily_kama, symbols, df_buffers.copy(), fee_rate, php_usd_rate, discord_webhook_url
                    )
                    closed_today.clear()
