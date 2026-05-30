import argparse
import os
import sys
import asyncio
from live.db import init_db, get_portfolio, get_pht_now
from live.csm_engine import connect_csm_websocket

def load_env() -> dict:
    env = dict(os.environ)
    if os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip().strip('"').strip("'")
        except Exception: pass
    return env

def main():
    env = load_env()
    parser = argparse.ArgumentParser(description="Live RG-CSM Portfolio Trading Engine")
    parser.add_argument('--initial-cash', type=float, default=500000.0)
    parser.add_argument('--php-usd-rate', type=float, default=58.5)
    parser.add_argument('--fee', type=float, default=0.001)
    
    default_webhook = env.get('DISCORD_WEBHOOK_URL', None)
    parser.add_argument('--discord-webhook', type=str, default=default_webhook)
    
    args = parser.parse_args()
    
    init_db(initial_cash_php=args.initial_cash)
    cash_php, holdings = get_portfolio()
    
    # 15 Assets used in the verified backtest
    symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
        'ADA/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT',
        'AVAX/USDT', 'LTC/USDT', 'ATOM/USDT', 'UNI/USDT', 'BCH/USDT'
    ]
    
    print("\n=======================================================")
    print("      LIVE KAMA PORTFOLIO ENGINE (PHP/PHT)             ")
    print("=======================================================")
    print(f"Start Time:      {get_pht_now()}")
    print(f"Trading Symbols: 15 Core Assets")
    print(f"Strategy:        Kaufman Adaptive Moving Average + Macro Gate")
    print(f"Exchange Rate:   ₱{args.php_usd_rate:.2f} PHP per 1 USD")
    print(f"Taker Fee Rate:  {args.fee * 100:.2f}%")
    print("-------------------------------------------------------")
    print(f"Current Portfolio Balance:")
    print(f" - PHP Cash:     ₱{cash_php:,.2f} PHP")
    for sym, amt in holdings.items():
        print(f" - {sym} Holdings: {amt:.6f}")
    print("=======================================================\n")

    try:
        asyncio.run(connect_csm_websocket(
            symbols=symbols,
            fee_rate=args.fee,
            php_usd_rate=args.php_usd_rate,
            discord_webhook_url=args.discord_webhook
        ))
    except (KeyboardInterrupt, SystemExit):
        print(f"\n[{get_pht_now()}] System shutdown signal received. Shutting down Live CSM Engine cleanly.")
        sys.exit(0)

if __name__ == '__main__':
    main()
