import pandas as pd
from data.loader import get_ohlcv

def run_test():
    print("=== RUNNING LIVE DATA INGESTION TEST ===\n")
    
    # Define test parameters
    symbol = 'BTC/USDT'
    timeframe = '1d'
    start_date = '2026-04-01'
    end_date = '2026-05-25'
    
    print(f"Query 1: Fetching {symbol} daily candles from {start_date} to {end_date} (Expect Cache Miss)...")
    df_fresh = get_ohlcv(symbol, timeframe, start_date, end_date)
    print(f"--> Retrieved {len(df_fresh)} candles.")
    print("--> Sample Data (First 3 rows):")
    print(df_fresh.head(3))
    print("\n" + "-"*50 + "\n")
    
    print(f"Query 2: Fetching the exact same query (Expect Cache Hit)...")
    import time
    start_time = time.time()
    df_cached = get_ohlcv(symbol, timeframe, start_date, end_date)
    elapsed = time.time() - start_time
    print(f"--> Retrieved {len(df_cached)} candles in {elapsed:.4f} seconds.")
    
    # Verify exact match
    match = df_fresh.equals(df_cached)
    print(f"--> Cached matches Fresh exactly: {match}")
    print("\n=========================================")

if __name__ == "__main__":
    run_test()
