import os
import time
from typing import Optional, List, Any
import ccxt
import pandas as pd

def _sanitize_date_for_filename(date_str: Optional[str]) -> str:
    """
    Sanitize the date string to be safe for filenames and deterministic.
    
    Args:
        date_str: Date string to sanitize.
        
    Returns:
        A sanitized string representing the date.
    """
    if not date_str:
        return "none"
    try:
        dt = pd.to_datetime(date_str, utc=True)
        return dt.strftime("%Y%m%d_%H%M%S")
    except Exception:
        # Fallback: remove characters that might be invalid for filenames
        sanitized = str(date_str)
        for char in ['/', ':', ' ', '\\', '*', '?', '"', '<', '>', '|']:
            sanitized = sanitized.replace(char, '_')
        return sanitized

def _fetch_with_retry(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    since: Optional[int] = None,
    limit: Optional[int] = None,
    max_retries: int = 5,
    backoff_factor: float = 2.0
) -> List[List[Any]]:
    """
    Fetch OHLCV candles from the exchange with retry logic and exponential backoff.
    
    Args:
        exchange: The CCXT exchange instance.
        symbol: Ticker symbol (e.g. 'BTC/USDT').
        timeframe: Timeframe (e.g. '1d', '1h').
        since: Milliseconds timestamp for the start date.
        limit: Max candles to fetch per call.
        max_retries: Number of retry attempts.
        backoff_factor: Multiplier for retry delays.
        
    Returns:
        List of OHLCV candles: [[timestamp, open, high, low, close, volume], ...].
        
    Raises:
        ccxt.BaseError: If all retries fail or a non-retryable error occurs.
    """
    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            # fetch_ohlcv returns list of lists (candles)
            data = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            return data if data is not None else []
        except (ccxt.NetworkError, ccxt.RateLimitExceeded, ccxt.RequestTimeout) as e:
            if attempt == max_retries:
                print(f"Error: Max retries ({max_retries}) reached. Raising error.")
                raise e
            print(f"Network warning (attempt {attempt}/{max_retries}): {e}. Retrying in {delay:.2f}s...")
            time.sleep(delay)
            delay *= backoff_factor
        except ccxt.ExchangeError as e:
            # Check for non-retryable errors like BadSymbol or authentication errors
            if isinstance(e, (ccxt.AuthenticationError, ccxt.PermissionDenied, ccxt.BadSymbol)):
                raise e
            if attempt == max_retries:
                raise e
            print(f"Exchange warning (attempt {attempt}/{max_retries}): {e}. Retrying in {delay:.2f}s...")
            time.sleep(delay)
            delay *= backoff_factor
            
    return []

def get_ohlcv(
    symbol: str,
    timeframe: str = '1d',
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    exchange_name: str = 'binance'
) -> pd.DataFrame:
    """
    Get historical OHLCV data for a given symbol and timeframe.
    
    This function checks if the requested data exists in the local cache. If it
    does, it loads it from disk. If not, it downloads the data from the specified
    exchange using CCXT, saves it to the cache directory, and then returns it.
    
    Args:
        symbol: Ticker symbol (e.g. 'BTC/USDT').
        timeframe: Candle timeframe (e.g. '1d', '1h').
        start_date: Start date string (e.g., '2025-01-01' or ISO-8601).
        end_date: End date string (e.g., '2025-02-01' or ISO-8601).
        exchange_name: Name of the CCXT exchange to use (default: 'binance').
        
    Returns:
        A Pandas DataFrame with DatetimeIndex named 'Timestamp' and columns:
        ['Open', 'High', 'Low', 'Close', 'Volume'].
        
    Raises:
        ValueError: If the exchange is not supported.
        NotImplementedError: If the exchange does not support fetchOHLCV.
    """
    # 1. Setup cache path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(base_dir, '.cache')
    os.makedirs(cache_dir, exist_ok=True)
    
    # Sanitize inputs for filename
    safe_symbol = symbol.replace('/', '_').replace(':', '_')
    start_str = _sanitize_date_for_filename(start_date)
    end_str = _sanitize_date_for_filename(end_date)
    cache_filename = f"{exchange_name}_{safe_symbol}_{timeframe}_{start_str}_{end_str}.csv"
    cache_path = os.path.join(cache_dir, cache_filename)
    
    # 2. Check if cache exists
    if os.path.exists(cache_path):
        print(f"Loading cached data from {cache_path}")
        df = pd.read_csv(cache_path, index_col='Timestamp')
        df.index = pd.to_datetime(df.index, utc=True)
        return df
        
    # 3. If cache miss, fetch fresh data
    print(f"Cache miss. Fetching fresh data from {exchange_name} for {symbol} ({timeframe})...")
    
    if not hasattr(ccxt, exchange_name):
        raise ValueError(f"Exchange '{exchange_name}' is not supported by ccxt.")
        
    exchange_class = getattr(ccxt, exchange_name)
    exchange = exchange_class({'enableRateLimit': True})
    
    if not exchange.has.get('fetchOHLCV', False):
        raise NotImplementedError(f"Exchange '{exchange_name}' does not support fetchOHLCV.")
        
    # Parse dates to milliseconds timestamp
    since = None
    if start_date:
        since = int(pd.to_datetime(start_date, utc=True).timestamp() * 1000)
        
    end_ms = None
    if end_date:
        end_ms = int(pd.to_datetime(end_date, utc=True).timestamp() * 1000)
        
    all_candles = []
    current_since = since
    limit = 1000
    
    while True:
        try:
            candles = _fetch_with_retry(exchange, symbol, timeframe, since=current_since, limit=limit)
            if not candles:
                break
                
            all_candles.extend(candles)
            
            last_timestamp = candles[-1][0]
            
            # Stop if we fetched past end date
            if end_ms is not None and last_timestamp >= end_ms:
                break
                
            # Stop if we received fewer candles than the limit (we reached the end of available data)
            if len(candles) < limit:
                break
                
            next_since = last_timestamp + 1
            if current_since is not None and next_since <= current_since:
                break
                
            current_since = next_since
            time.sleep(exchange.rateLimit / 1000.0)
            
        except Exception as e:
            print(f"Error during fetching loop: {e}")
            raise e
            
    # Process fetched candles
    if not all_candles:
        print(f"No candles retrieved for {symbol} on {exchange_name}.")
        df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
        df.index = pd.to_datetime([], utc=True)
        df.index.name = 'Timestamp'
        return df
        
    # Parse list of lists to DataFrame
    df = pd.DataFrame(all_candles, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms', utc=True)
    df.set_index('Timestamp', inplace=True)
    
    # Remove any potential duplicate indexes
    df = df[~df.index.duplicated(keep='first')]
    
    # Filter strictly within requested bounds
    if start_date:
        start_dt = pd.to_datetime(start_date, utc=True)
        df = df[df.index >= start_dt]
    if end_date:
        end_dt = pd.to_datetime(end_date, utc=True)
        df = df[df.index <= end_dt]
        
    # Save to local CSV cache
    df.to_csv(cache_path)
    print(f"Saved {len(df)} candles to cache: {cache_path}")
    
    return df
