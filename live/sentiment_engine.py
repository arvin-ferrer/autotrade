import feedparser
import re
import os
import json
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()
import os
import json
from google import genai
from google.genai import types



def fetch_crypto_news(symbol: str, limit: int = 15) -> list:
    feeds = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://crypto.news/rss",
        "https://cryptopotato.com/feed/",
        "https://dailyhodl.com/crypto/feed",
        "https://bitcoinmagazine.com/feed/all",
        "https://cryptonews.com/news/bitcoin/rss.xml",
        "https://decrypt.co/rss",
        "https://cointelegraph.com/rss",
        "https://www.theblockcrypto.com/feed"
    ]
    clean_symbol = symbol.split('/')[0].upper()
    name_map = {                                                                            
        "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",                               
        "ADA": "Cardano", "DOGE": "Dogecoin", "LINK": "Chainlink", "DOT": "Polkadot"        
    }                                                                                       
    coin_name = name_map.get(clean_symbol, clean_symbol)                         
    ticker_pattern = re.compile(rf"\b{clean_symbol}\b")                                     
    
    print(f"Scanning public RSS feeds for {coin_name} ({clean_symbol}) news...")
    headlines = []
        
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title
                if ticker_pattern.search(title) or coin_name.upper() in title.upper():      
                    headlines.append(title)
        except Exception as e:
            print(f"Failed to parse feed {url}: {e}")
                
    unique_headlines = list(set(headlines))
    return unique_headlines[:limit]
  
def analyze_sentiment_with_llm(symbol: str, headlines: list) -> dict:                       
    """                                                                                     
    Passes the headlines to Gemini to generate a quantitative sentiment score.              
    Returns a dictionary with 'sentiment_score' and 'reason'.                               
    """                                                                                     
    if not headlines:                                                                       
        return {"sentiment_score": 0.0, "reason": "No news found."}                         
                                                                                            
    # Grab the Gemini API key from your .env                                                
    api_key = os.getenv("GEMINI_API_KEY")                                                   
    if not api_key:                                                                         
        print("Error: GEMINI_API_KEY not found in .env")                                    
        return {"sentiment_score": 0.0, "reason": "Missing API Key"}                        
                                                                                            
    client = genai.Client(api_key=api_key)                                                  
                                                                                            
    # Format the headlines into a clean text block                                          
    news_text = "\n".join([f"- {h}" for h in headlines])                                    
                                                                                            
    prompt = f"""                                                                           
    You are a quantitative finance sentiment analyzer for cryptocurrency trading.           
    Read the following recent news headlines for {symbol}:                                  
                                                                                            
    {news_text}                                                                             
                                                                                            
    Output a strictly valid JSON object with exactly two keys:                              
    1. "sentiment_score": A float between -1.0 (Extremely Bearish) and 1.0 (Extremely       
    Bullish). 0.0 is neutral.                                                                     
    2. "reason": A brief 1-sentence explanation of why you gave that score.                 
    """                                                                                     
                                                                                            
    try:                                                                                    
        # Attempt the primary, smarter model first
        response = client.models.generate_content(                                          
            model='gemini-2.5-pro',                                                       
            contents=prompt,                                                                
            config=types.GenerateContentConfig(                                             
                response_mime_type="application/json"                                       
            ),                                                                              
        )                                                                                   
        result = json.loads(response.text)                                                  
        return result                                                                       
    except Exception as e:                                                                  
        print(f"Primary LLM (Pro) failed: {e}. Falling back to Gemini Flash...")
        try:
            # Fallback to the much faster/cheaper Flash model if Pro hits a rate limit
            response = client.models.generate_content(                                          
                model='gemini-2.5-flash',                                                       
                contents=prompt,                                                                
                config=types.GenerateContentConfig(                                             
                    response_mime_type="application/json"                                       
                ),                                                                              
            )                                                                                   
            result = json.loads(response.text)                                                  
            return result
        except Exception as e_flash:
            print(f"Fallback LLM (Flash) also failed: {e_flash}")
            return {"sentiment_score": 0.0, "reason": "LLM Error"}

    # --- Execution Block ---
if __name__ == "__main__":
    import argparse
    import time
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', type=str, required=True, help="Comma separated list of symbols")
    args = parser.parse_args()
    
    symbols = [s.strip() for s in args.symbols.split(',')]
    
    # 1. Fetch ALL new data first
    new_results = {}
    for target_symbol in symbols:
        headlines = fetch_crypto_news(target_symbol, limit=15)
        print(f"\nFetched {len(headlines)} headlines for {target_symbol}.")
        
        sentiment_data = analyze_sentiment_with_llm(target_symbol, headlines)
        sentiment_data["timestamp"] = time.time()  # Per-symbol timestamp
        new_results[target_symbol] = sentiment_data
        
        print(f"=== {target_symbol} RAG Output ===")
        print(f"Sentiment Score: {sentiment_data.get('sentiment_score')}")
        print(f"Reason: {sentiment_data.get('reason')}")

    # 2. Lock, Read, Merge, Write
    import fcntl
    os.makedirs("data", exist_ok=True)
    lock_path = "data/daily_sentiment.lock"
    
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            final_data = {
                "timestamp": time.time(),
                "data": {}
            }
            if os.path.exists("data/daily_sentiment.json"):
                try:
                    with open("data/daily_sentiment.json", "r") as f:
                        existing_data = json.load(f)
                        final_data["data"] = existing_data.get("data", {})
                except Exception as e:
                    print(f"Could not load existing sentiment data: {e}")
            
            # Merge
            for sym, data in new_results.items():
                final_data["data"][sym] = data
            
            # Atomic Save with PID to prevent tmp file collisions
            tmp_path = f"data/daily_sentiment_tmp_{os.getpid()}.json"
            with open(tmp_path, "w") as f:
                json.dump(final_data, f, indent=4)
            os.replace(tmp_path, "data/daily_sentiment.json")
            print("\nAtomic save to data/daily_sentiment.json complete!")
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)