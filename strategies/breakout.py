from typing import Optional
import numpy as np
import pandas as pd
from strategies.base import BaseStrategy
import os
import json

class AdaptiveHighBetaBreakoutStrategy(BaseStrategy):
    """
    Adaptive High-Beta Volatility Breakout Strategy.
    Timeframe: 4h
    """
    def __init__(self, name: str = "AdaptiveBreakout", params: Optional[dict] = None):
        super().__init__(name, params)
        self.atr_window = self.params.get('atr_window', 14)
        self.baseline_window = self.params.get('baseline_window', 50)
        self.donchian_window = self.params.get('donchian_window', 20)
        self.vol_threshold = self.params.get('vol_threshold', 1.0)
        
    def generate_signals(self, df: pd.DataFrame, symbol: str = None) -> pd.DataFrame:
        df_out = df.copy()
        
        min_len = max(self.atr_window + 1, self.baseline_window, self.donchian_window + 1)
        if len(df_out) < min_len:
            df_out['atr'] = np.nan
            df_out['atr_baseline'] = np.nan
            df_out['upper_channel'] = np.nan
            df_out['lower_channel'] = np.nan
            df_out['Signal'] = 0.0
            return df_out
            
        high_low = df_out['High'] - df_out['Low']
        high_close = np.abs(df_out['High'] - df_out['Close'].shift(1))
        low_close = np.abs(df_out['Low'] - df_out['Close'].shift(1))
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df_out['atr'] = true_range.ewm(alpha=1/self.atr_window, adjust=False).mean()
        
        df_out['atr_baseline'] = df_out['atr'].ewm(span=self.baseline_window, adjust=False).mean()
        
        df_out['upper_channel'] = df_out['High'].shift(1).rolling(self.donchian_window).max()
        df_out['lower_channel'] = df_out['Low'].shift(1).rolling(self.donchian_window).min()
        
        df_out['Signal'] = 0.0
        
        valid_mask = (df_out['atr'].notna() & 
                      df_out['atr_baseline'].notna() & 
                      df_out['upper_channel'].notna() & 
                      df_out['lower_channel'].notna())

        sentiment_score = 0.0

        try:
            if os.path.exists("data/daily_sentiment.json"):
                with open("data/daily_sentiment.json", "r") as f:
                    rag_data = json.load(f)
                    
                    if symbol and symbol in rag_data.get("data", {}):
                        sym_data = rag_data["data"][symbol]
                        import time
                        # Check if this specific symbol's data is fresh (less than 6 hours old)
                        if time.time() - sym_data.get("timestamp", 0) < 21600:
                            sentiment_score = float(sym_data.get("sentiment_score", 0.0))
        except Exception:
            pass

        # buy_condition = (df_out['Close'] > df_out['upper_channel']) & (df_out['atr'] > df_out['atr_baseline'] * self.vol_threshold)
        # sell_condition = (df_out['Close'] < df_out['lower_channel'])
        raw_buy = (df_out['Close'] > df_out['upper_channel']) & (df_out['atr'] > df_out['atr_baseline'] * self.vol_threshold)
        raw_sell = (df_out['Close'] < df_out['lower_channel']) & (df_out['atr'] > df_out['atr_baseline'] * self.vol_threshold)

        buy_condition = raw_buy & (sentiment_score >= -0.3)
        sell_condition = raw_sell & (sentiment_score <= 0.3)

        df_out.loc[valid_mask, 'Signal'] = np.where(
            buy_condition[valid_mask],
            1.0,
            np.where(
                sell_condition[valid_mask],
                -1.0,
                0.0
            )
        )
        
        return df_out