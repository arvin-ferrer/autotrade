import asyncio
import json
import time
import websockets
import pandas as pd
from typing import Optional, List
from data.loader import get_ohlcv
from live.executor import execute_live_signal, check_risk_limits, send_discord_alert
from live.db import get_pht_now

async def connect_binance_websocket(
    strategy,
    symbols: List[str],
    timeframe: str,
    fee_rate: float,
    php_usd_rate: float,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    discord_webhook_url: Optional[str] = None
) -> None:
    """
    Subscribes to Binance WebSocket stream for the given symbols and timeframe.
    Fetches historical candle buffers to bootstrap strategy indicators, and runs 
    the executor whenever a live candle closes.
    """
    ws_streams = [f"{sym.replace('/', '').lower()}@kline_{timeframe}" for sym in symbols]
    streams_path = "/".join(ws_streams)
    url = f"wss://stream.binance.com:9443/stream?streams={streams_path}"
    
    print(f"[{get_pht_now()}] Connecting to Binance WebSocket stream at {url}...")
    
    # Notify Discord bot startup
    send_discord_alert(
        webhook_url=discord_webhook_url,
        title="🤖 Live Paper Trading Bot Started",
        description=f"Now monitoring **{', '.join(symbols)}** on the **{timeframe}** timeframe.",
        color=3447003,  # Blue
        fields=[
            {"name": "Currency", "value": "PHP (₱)", "inline": True},
            {"name": "Exchange Rate", "value": f"₱{php_usd_rate:.2f} PHP/USD", "inline": True},
            {"name": "Fee Rate", "value": f"{fee_rate*100:.2f}%", "inline": True}
        ]
    )

    # 2. Start WebSocket Listening with Auto-reconnect loop
    retry_delay = 5
    while True:
        try:
            # 1. Fetch bootstrap buffer historical data inside the loop to prevent data gaps on reconnect
            print(f"[{get_pht_now()}] Fetching historical buffer candles to bootstrap indicators...")
            now = pd.Timestamp.now(tz='UTC')
            
            # Fetch enough candles to calculate slow MAs (e.g. 50 slows require at least 50 historical candles)
            if timeframe == '1m':
                start_dt = now - pd.Timedelta(minutes=150)
            elif timeframe == '5m':
                start_dt = now - pd.Timedelta(minutes=750)
            elif timeframe == '1h':
                start_dt = now - pd.Timedelta(hours=150)
            else:
                start_dt = now - pd.Timedelta(days=150)
                
            start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            df_buffers = {}
            
            # Map stream name back to symbol
            stream_to_symbol = {f"{sym.replace('/', '').lower()}@kline_{timeframe}": sym for sym in symbols}
            
            for symbol in symbols:
                try:
                    df_buffer = get_ohlcv(symbol, timeframe, start_date=start_str)
                    print(f"[{get_pht_now()}] Loaded {len(df_buffer)} buffer candles for {symbol}.")
                    df_buffers[symbol] = df_buffer
                except Exception as e:
                    print(f"[{get_pht_now()}] Error loading bootstrap candles for {symbol}: {e}. Starting with empty cache.")
                    df_buffers[symbol] = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
                    df_buffers[symbol].index.name = 'Timestamp'

            async with websockets.connect(url) as websocket:
                print(f"[{get_pht_now()}] Connected! Listening for real-time ticks...")
                
                async for message in websocket:
                    event = json.loads(message)
                    if 'data' not in event:
                        continue
                        
                    stream_name = event['stream']
                    data = event['data']
                    kline = data['k']
                    
                    symbol_k = stream_to_symbol.get(stream_name)
                    if not symbol_k:
                        continue
                        
                    is_closed = kline['x']  # True if candle has finished closing
                    close_price = float(kline['c'])
                    timestamp_ms = kline['t']
                    dt = pd.to_datetime(timestamp_ms, unit='ms', utc=True)
                    
                    # Print ticks to terminal in-place
                    print(
                        f"\r[{get_pht_now()}] {symbol_k} Tick: {dt.strftime('%Y-%m-%d %H:%M:%S')} | "
                        f"Price: ${close_price:,.2f} USD (₱{close_price * php_usd_rate:,.2f} PHP) | "
                        f"Closed: {is_closed}", end="", flush=True
                    )
                    
                    # Evaluate risk limits instantly on the live tick
                    await asyncio.to_thread(
                        check_risk_limits,
                        symbol=symbol_k,
                        current_price=close_price,
                        fee_rate=fee_rate,
                        php_usd_rate=php_usd_rate,
                        stop_loss_pct=stop_loss_pct,
                        take_profit_pct=take_profit_pct,
                        discord_webhook_url=discord_webhook_url
                    )
                    
                    if is_closed:
                        # Print newline to keep ticks clean
                        print()
                        print(f"[{get_pht_now()}] {symbol_k} Candle Closed! Parsing new candle data...")
                        
                        # Create new kline row
                        new_row = pd.DataFrame([{
                            'Open': float(kline['o']),
                            'High': float(kline['h']),
                            'Low': float(kline['l']),
                            'Close': float(kline['c']),
                            'Volume': float(kline['v'])
                        }], index=[dt])
                        new_row.index.name = 'Timestamp'
                        
                        # Append and manage buffer size
                        df_buffer = df_buffers[symbol_k]
                        df_buffer = pd.concat([df_buffer, new_row])
                        df_buffer = df_buffer[~df_buffer.index.duplicated(keep='last')]
                        df_buffer = df_buffer.tail(200)  # Keep last 200 rows to optimize memory
                        df_buffers[symbol_k] = df_buffer
                        
                        # Generate strategy signals
                        df_signals = strategy.generate_signals(df_buffer)
                        
                        # Execute trade checking in a separate thread to prevent blocking the async loop
                        await asyncio.to_thread(
                            execute_live_signal,
                            df=df_signals,
                            symbol=symbol_k,
                            fee_rate=fee_rate,
                            php_usd_rate=php_usd_rate,
                            discord_webhook_url=discord_webhook_url
                        )
                        
        except (websockets.ConnectionClosed, Exception) as e:
            print() # Print newline after inline tick prints
            print(f"[{get_pht_now()}] WebSocket warning: {e}. Reconnecting in {retry_delay}s...")
            # Alert Discord about reconnection
            send_discord_alert(
                webhook_url=discord_webhook_url,
                title="⚠️ Live Trading Bot Connection Warning",
                description=f"WebSocket disconnected: `{e}`. Attempting reconnection in {retry_delay}s...",
                color=16768000, # Orange
                fields=[]
            )
            await asyncio.sleep(retry_delay)
            # Simple exponential backoff cap
            retry_delay = min(retry_delay * 2, 60)
            
def start_live_session(
    strategy,
    symbols: List[str],
    timeframe: str = '1m',
    fee_rate: float = 0.001,
    php_usd_rate: float = 58.5,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    discord_webhook_url: Optional[str] = None
) -> None:
    """Entrypoint to run the async WebSocket connection loop."""
    try:
        asyncio.run(connect_binance_websocket(
            strategy=strategy,
            symbols=symbols,
            timeframe=timeframe,
            fee_rate=fee_rate,
            php_usd_rate=php_usd_rate,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            discord_webhook_url=discord_webhook_url
        ))
    except KeyboardInterrupt:
        print(f"\n[{get_pht_now()}] KeyboardInterrupt received. Shutting down Live Session cleanly.")
        send_discord_alert(
            webhook_url=discord_webhook_url,
            title="🛑 Live Paper Trading Bot Stopped",
            description="The live trading bot process was manually terminated.",
            color=15158332, # Red
            fields=[]
        )
