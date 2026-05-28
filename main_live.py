import argparse
import os
import sys
from strategies import CrossoverStrategy, RSIStrategy, MACDStrategy, EnsembleStrategy, VolumeRSIStrategy
from live.db import init_db, get_portfolio, get_pht_now
from live.runner import start_live_session

def load_env() -> dict:
    """Helper to parse a local .env file if it exists without requiring python-dotenv"""
    env = {}
    if os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        # Strip potential quotes
                        env[k.strip()] = v.strip().strip('"').strip("'")
        except Exception as e:
            print(f"[Warning] Failed to load .env file: {e}")
    return env

import json
import urllib.request

def get_live_php_usd_rate(fallback_rate: float) -> float:
    """Fetches the real-time USD/PHP exchange rate from the keyless Frankfurter API"""
    url = "https://api.frankfurter.app/latest?from=USD&to=PHP"
    print(f"[{get_pht_now()}] Fetching real-time USD/PHP exchange rate from Frankfurter API...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            rate = float(data['rates']['PHP'])
            print(f"[FX API] Loaded real-time rate: ₱{rate:.4f} PHP")
            return rate
    except Exception as e:
        print(f"[FX API Warning] Failed to fetch real-time rate: {e}. Using fallback: ₱{fallback_rate:.2f} PHP")
        return fallback_rate

def main():
    # Load env variables first
    env = load_env()
    
    parser = argparse.ArgumentParser(description="Binance Live Paper Trading Bot (PHP & PHT Timezone)")
    
    # Live settings
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help="Symbol(s) to trade, comma separated (default: BTC/USDT)")
    parser.add_argument('--timeframe', type=str, default='1m', help="Kline timeframe to monitor (default: 1m)")
    parser.add_argument('--strategy', type=str, default='crossover', choices=['crossover', 'rsi', 'macd', 'ensemble', 'volumersi'], 
                        help="Strategy to run (default: crossover)")
    
    # Capital & Local Conversion settings
    parser.add_argument('--initial-cash', type=float, default=500000.0, 
                        help="Initial cash in PHP if DB is fresh (default: 500000.0 PHP)")
    
    # Risk settings
    parser.add_argument('--stop-loss', type=float, default=None, help="Stop loss percentage as float (e.g. 0.02 = 2%%)")
    parser.add_argument('--take-profit', type=float, default=None, help="Take profit percentage as float (e.g. 0.05 = 5%%)")
    
    # Read conversion rate: command-line arg -> live API -> .env file -> fallback 58.5
    parser.add_argument('--php-usd-rate', type=float, default=None, 
                        help="PHP/USD conversion rate. If omitted, fetches live rate automatically.")
    
    parser.add_argument('--fee', type=float, default=0.001, help="Transaction fee rate (e.g. 0.001 = 0.1%%) (default: 0.001)")
    
    # Read Discord Webhook: command-line arg -> .env file -> None
    default_webhook = env.get('DISCORD_WEBHOOK_URL', None)
    parser.add_argument('--discord-webhook', type=str, default=default_webhook, 
                        help="Discord Webhook URL for trading notifications")
    
    # MA indicators
    parser.add_argument('--fast-window', type=int, default=20)
    parser.add_argument('--slow-window', type=int, default=50)
    parser.add_argument('--ma-type', type=str, default='sma', choices=['sma', 'ema'])
    
    # RSI indicators
    parser.add_argument('--rsi-window', type=int, default=14)
    parser.add_argument('--rsi-overbought', type=float, default=70.0)
    parser.add_argument('--rsi-oversold', type=float, default=30.0)
    
    # Volume Filter indicators
    parser.add_argument('--vol-ma-window', type=int, default=20)
    parser.add_argument('--vol-multiplier', type=float, default=1.5)
    
    # MACD indicators
    parser.add_argument('--macd-fast', type=int, default=12)
    parser.add_argument('--macd-slow', type=int, default=26)
    parser.add_argument('--macd-signal', type=int, default=9)
    
    # Ensemble indicators
    parser.add_argument('--ensemble-rules', type=str, default='macd_rsi', choices=['macd_rsi', 'ema_rsi', 'triple'])
    
    args = parser.parse_args()
    
    # Determine PHP/USD Rate dynamically
    env_rate = float(env.get('PHP_USD_RATE', 58.5))
    if args.php_usd_rate is None:
        php_usd_rate = get_live_php_usd_rate(env_rate)
    else:
        php_usd_rate = args.php_usd_rate
    
    # Initialize SQLite Database
    init_db(initial_cash_php=args.initial_cash)
    
    # Fetch current portfolio balance from SQLite database
    cash_php, holdings = get_portfolio()
    
    symbols = [s.strip() for s in args.symbol.split(',')]
    
    print("\n=======================================================")
    print("      LIVE CRYPTO PAPER TRADING CLIENT (PHP/PHT)       ")
    print("=======================================================")
    print(f"Start Time:      {get_pht_now()}")
    print(f"Exchange:        Binance Spot (Real-time WebSockets)")
    print(f"Trading Symbols: {', '.join(symbols)}")
    print(f"Timeframe:       {args.timeframe}")
    print(f"Strategy:        {args.strategy.upper()}")
    print(f"Exchange Rate:   ₱{php_usd_rate:.2f} PHP per 1 USD")
    print(f"Taker Fee Rate:  {args.fee * 100:.2f}%")
    print(f"Notification:    {'ENABLED (Discord Webhook)' if args.discord_webhook else 'DISABLED'}")
    print("-------------------------------------------------------")
    print(f"Current Portfolio Balance:")
    print(f" - PHP Cash:     ₱{cash_php:,.2f} PHP")
    for sym, amt in holdings.items():
        print(f" - {sym} Holdings: {amt:.6f}")
    print("=======================================================\n")
    
    # Instantiate strategy
    if args.strategy == 'crossover':
        params = {
            'fast_window': args.fast_window,
            'slow_window': args.slow_window,
            'ma_type': args.ma_type
        }
        strategy = CrossoverStrategy(name=f"{args.ma_type.upper()}_Crossover", params=params)
    elif args.strategy == 'rsi':
        params = {
            'window': args.rsi_window,
            'overbought': args.rsi_overbought,
            'oversold': args.rsi_oversold
        }
        strategy = RSIStrategy(name="RSI_Momentum", params=params)
    elif args.strategy == 'macd':
        params = {
            'fast_period': args.macd_fast,
            'slow_period': args.macd_slow,
            'signal_period': args.macd_signal
        }
        strategy = MACDStrategy(name="MACD_Crossover", params=params)
    elif args.strategy == 'volumersi':
        params = {
            'rsi_window': args.rsi_window,
            'overbought': args.rsi_overbought,
            'oversold': args.rsi_oversold,
            'vol_ma_window': args.vol_ma_window,
            'vol_multiplier': args.vol_multiplier
        }
        strategy = VolumeRSIStrategy(name="Volume_RSI_Breakout", params=params)
    else: # ensemble
        params = {
            'fast_window': args.fast_window,
            'slow_window': args.slow_window,
            'ma_type': args.ma_type,
            'rsi_window': args.rsi_window,
            'rsi_overbought': args.rsi_overbought,
            'rsi_oversold': args.rsi_oversold,
            'macd_fast': args.macd_fast,
            'macd_slow': args.macd_slow,
            'macd_signal': args.macd_signal,
            'rules': args.ensemble_rules
        }
        strategy = EnsembleStrategy(name=f"Ensemble_{args.ensemble_rules}", params=params)
        
    # Start loop
    start_live_session(
        strategy=strategy,
        symbols=symbols,
        timeframe=args.timeframe,
        fee_rate=args.fee,
        php_usd_rate=php_usd_rate,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        discord_webhook_url=args.discord_webhook
    )

if __name__ == '__main__':
    main()
