from typing import Optional
import numpy as np
import pandas as pd
from strategies.base import BaseStrategy

class CrossoverStrategy(BaseStrategy):
    """
    Moving Average Crossover Strategy.
    
    Generates a Buy signal (1.0) when the Fast Moving Average is greater than
    the Slow Moving Average, and a Sell signal (-1.0) when the Fast Moving Average
    is less than or equal to the Slow Moving Average.
    """
    def __init__(self, name: str = "Crossover", params: Optional[dict] = None):
        super().__init__(name, params)
        self.fast_window = self.params.get('fast_window', 20)
        self.slow_window = self.params.get('slow_window', 50)
        self.ma_type = self.params.get('ma_type', 'sma').lower()
        
        if self.ma_type not in ['sma', 'ema']:
            raise ValueError(f"ma_type must be either 'sma' or 'ema', got '{self.ma_type}'")
            
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates moving averages and generates crossover signals.
        
        Args:
            df: Input price DataFrame.
            
        Returns:
            DataFrame with indicator columns and a 'Signal' column.
        """
        # Work on a copy to avoid side effects
        df_out = df.copy()
        
        # Handle small DataFrames
        if len(df_out) < self.slow_window:
            df_out['fast_ma'] = np.nan
            df_out['slow_ma'] = np.nan
            df_out['Signal'] = 0.0
            return df_out
            
        # Calculate moving averages
        if self.ma_type == 'sma':
            df_out['fast_ma'] = df_out['Close'].rolling(window=self.fast_window).mean()
            df_out['slow_ma'] = df_out['Close'].rolling(window=self.slow_window).mean()
        else: # ema
            df_out['fast_ma'] = df_out['Close'].ewm(span=self.fast_window, adjust=False).mean()
            df_out['slow_ma'] = df_out['Close'].ewm(span=self.slow_window, adjust=False).mean()
            
        # Generate signals
        df_out['Signal'] = 0.0
        
        # Only compare when both MAs are non-NaN (handles SMA rolling window ramp-up)
        valid_mask = df_out['fast_ma'].notna() & df_out['slow_ma'].notna()
        df_out.loc[valid_mask, 'Signal'] = np.where(
            df_out.loc[valid_mask, 'fast_ma'] > df_out.loc[valid_mask, 'slow_ma'],
            1.0,
            -1.0
        )
        
        return df_out


class RSIStrategy(BaseStrategy):
    """
    Relative Strength Index (RSI) Strategy.
    
    Generates a Buy signal (1.0) when RSI is below the oversold threshold (e.g. 30),
    a Sell signal (-1.0) when RSI is above the overbought threshold (e.g. 70),
    and Hold/Neutral (0.0) otherwise.
    """
    def __init__(self, name: str = "RSI", params: Optional[dict] = None):
        super().__init__(name, params)
        self.window = self.params.get('window', 14)
        self.overbought = self.params.get('overbought', 70)
        self.oversold = self.params.get('oversold', 30)
        
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates RSI and generates threshold-based signals.
        
        Args:
            df: Input price DataFrame.
            
        Returns:
            DataFrame with indicator columns and a 'Signal' column.
        """
        df_out = df.copy()
        
        # Handle small DataFrames (needs at least window + 1 for diff/RSI calculation)
        if len(df_out) <= self.window:
            df_out['rsi'] = np.nan
            df_out['Signal'] = 0.0
            return df_out
            
        # Calculate Wilder's RSI using pure Pandas
        delta = df_out['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        # Exponential moving average with Wilder's smoothing alpha = 1 / window
        avg_gain = gain.ewm(alpha=1 / self.window, min_periods=self.window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.window, min_periods=self.window, adjust=False).mean()
        
        # Avoid division by zero
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        df_out['rsi'] = 100.0 - (100.0 / (1.0 + rs))
        
        # Generate signals
        df_out['Signal'] = 0.0
        
        # Only set signal when RSI is not NaN
        valid_mask = df_out['rsi'].notna()
        df_out.loc[valid_mask, 'Signal'] = np.where(
            df_out.loc[valid_mask, 'rsi'] < self.oversold,
            1.0,
            np.where(
                df_out.loc[valid_mask, 'rsi'] > self.overbought,
                -1.0,
                0.0
            )
        )
        
        return df_out


class MACDStrategy(BaseStrategy):
    """
    Moving Average Convergence Divergence (MACD) Crossover Strategy.
    
    Generates a Buy signal (1.0) when the MACD line is above the Signal line,
    and a Sell signal (-1.0) when the MACD line is below or equal to the Signal line.
    """
    def __init__(self, name: str = "MACD", params: Optional[dict] = None):
        super().__init__(name, params)
        self.fast_period = self.params.get('fast_period', 12)
        self.slow_period = self.params.get('slow_period', 26)
        self.signal_period = self.params.get('signal_period', 9)
        
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates MACD indicators and generates signal crossovers.
        
        Args:
            df: Input price DataFrame.
            
        Returns:
            DataFrame with indicator columns and a 'Signal' column.
        """
        df_out = df.copy()
        
        # Need at least slow_period + signal_period to calculate indicators
        if len(df_out) < (self.slow_period + self.signal_period):
            df_out['macd_line'] = np.nan
            df_out['signal_line'] = np.nan
            df_out['macd_hist'] = np.nan
            df_out['Signal'] = 0.0
            return df_out
            
        # Calculate Fast and Slow EMAs of Close price
        ema_fast = df_out['Close'].ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = df_out['Close'].ewm(span=self.slow_period, adjust=False).mean()
        
        # Calculate MACD Line
        df_out['macd_line'] = ema_fast - ema_slow
        
        # Calculate Signal Line (EMA of MACD Line)
        df_out['signal_line'] = df_out['macd_line'].ewm(span=self.signal_period, adjust=False).mean()
        
        # Calculate MACD Histogram
        df_out['macd_hist'] = df_out['macd_line'] - df_out['signal_line']
        
        # Generate Signals
        df_out['Signal'] = 0.0
        
        # Only set signal when both lines are non-NaN
        valid_mask = df_out['macd_line'].notna() & df_out['signal_line'].notna()
        df_out.loc[valid_mask, 'Signal'] = np.where(
            df_out.loc[valid_mask, 'macd_line'] > df_out.loc[valid_mask, 'signal_line'],
            1.0,
            -1.0
        )
        
        return df_out


class EnsembleStrategy(BaseStrategy):
    """
    Ensemble trading strategy combining Multiple Indicators (MAs, RSI, and MACD).
    
    Rule Options (specified in params['rules']):
    - 'macd_rsi': Buy on MACD crossover if RSI is not overbought (< overbought threshold).
                  Sell on MACD crossunder OR RSI > overbought threshold.
    - 'ema_rsi': Buy on EMA crossover if RSI is not overbought (< overbought threshold).
                 Sell on EMA crossunder OR RSI > overbought threshold.
    - 'triple': Buy when MACD is bullish AND Fast MA > Slow MA AND RSI is not overbought.
                Sell when MACD <= Signal OR Fast MA <= Slow MA OR RSI >= overbought.
    """
    def __init__(self, name: str = "Ensemble", params: Optional[dict] = None):
        super().__init__(name, params)
        self.fast_window = self.params.get('fast_window', 20)
        self.slow_window = self.params.get('slow_window', 50)
        self.ma_type = self.params.get('ma_type', 'ema').lower()
        self.rsi_window = self.params.get('rsi_window', 14)
        self.rsi_overbought = self.params.get('rsi_overbought', 70.0)
        self.rsi_oversold = self.params.get('rsi_oversold', 30.0)
        self.macd_fast = self.params.get('macd_fast', 12)
        self.macd_slow = self.params.get('macd_slow', 26)
        self.macd_signal = self.params.get('macd_signal', 9)
        self.rules = self.params.get('rules', 'macd_rsi').lower()
        
        if self.ma_type not in ['sma', 'ema']:
            raise ValueError(f"ma_type must be 'sma' or 'ema', got '{self.ma_type}'")
        if self.rules not in ['macd_rsi', 'ema_rsi', 'triple']:
            raise ValueError(f"rules must be 'macd_rsi', 'ema_rsi', or 'triple', got '{self.rules}'")
            
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        
        min_len = max(self.slow_window, self.rsi_window + 1, self.macd_slow + self.macd_signal)
        if len(df_out) < min_len:
            df_out['fast_ma'] = np.nan
            df_out['slow_ma'] = np.nan
            df_out['rsi'] = np.nan
            df_out['macd_line'] = np.nan
            df_out['signal_line'] = np.nan
            df_out['Signal'] = 0.0
            return df_out
            
        # 1. Calculate moving averages
        if self.ma_type == 'sma':
            df_out['fast_ma'] = df_out['Close'].rolling(window=self.fast_window).mean()
            df_out['slow_ma'] = df_out['Close'].rolling(window=self.slow_window).mean()
        else: # ema
            df_out['fast_ma'] = df_out['Close'].ewm(span=self.fast_window, adjust=False).mean()
            df_out['slow_ma'] = df_out['Close'].ewm(span=self.slow_window, adjust=False).mean()
            
        # 2. Calculate RSI
        delta = df_out['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / self.rsi_window, min_periods=self.rsi_window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.rsi_window, min_periods=self.rsi_window, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        df_out['rsi'] = 100.0 - (100.0 / (1.0 + rs))
        
        # 3. Calculate MACD
        ema_fast = df_out['Close'].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = df_out['Close'].ewm(span=self.macd_slow, adjust=False).mean()
        df_out['macd_line'] = ema_fast - ema_slow
        df_out['signal_line'] = df_out['macd_line'].ewm(span=self.macd_signal, adjust=False).mean()
        
        # 4. Generate Signals
        df_out['Signal'] = 0.0
        
        # Determine valid indicators masks
        valid_mask = (
            df_out['fast_ma'].notna() & 
            df_out['slow_ma'].notna() & 
            df_out['rsi'].notna() & 
            df_out['macd_line'].notna() & 
            df_out['signal_line'].notna()
        )
        
        # Apply Rules
        if self.rules == 'macd_rsi':
            df_out.loc[valid_mask, 'Signal'] = np.where(
                (df_out.loc[valid_mask, 'macd_line'] > df_out.loc[valid_mask, 'signal_line']) & 
                (df_out.loc[valid_mask, 'rsi'] < self.rsi_overbought),
                1.0,
                -1.0
            )
        elif self.rules == 'ema_rsi':
            df_out.loc[valid_mask, 'Signal'] = np.where(
                (df_out.loc[valid_mask, 'fast_ma'] > df_out.loc[valid_mask, 'slow_ma']) & 
                (df_out.loc[valid_mask, 'rsi'] < self.rsi_overbought),
                1.0,
                -1.0
            )
        elif self.rules == 'triple':
            df_out.loc[valid_mask, 'Signal'] = np.where(
                (df_out.loc[valid_mask, 'macd_line'] > df_out.loc[valid_mask, 'signal_line']) & 
                (df_out.loc[valid_mask, 'fast_ma'] > df_out.loc[valid_mask, 'slow_ma']) & 
                (df_out.loc[valid_mask, 'rsi'] < self.rsi_overbought),
                1.0,
                -1.0
            )
            
        return df_out


class VolumeRSIStrategy(BaseStrategy):
    """
    RSI Strategy with a Volume Confirmation Filter.
    
    Generates a Buy signal (1.0) when RSI is < oversold AND Current Volume > Volume MA * Multiplier.
    Generates a Sell signal (-1.0) when RSI is > overbought AND Current Volume > Volume MA * Multiplier.
    """
    def __init__(self, name: str = "VolumeRSI", params: Optional[dict] = None):
        super().__init__(name, params)
        self.rsi_window = self.params.get('rsi_window', 14)
        self.overbought = self.params.get('overbought', 70)
        self.oversold = self.params.get('oversold', 30)
        self.vol_ma_window = self.params.get('vol_ma_window', 20)
        self.vol_multiplier = self.params.get('vol_multiplier', 1.5)
        
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df_out = df.copy()
        
        min_len = max(self.rsi_window + 1, self.vol_ma_window + 1)
        if len(df_out) < min_len:
            df_out['rsi'] = np.nan
            df_out['vol_ma'] = np.nan
            df_out['Signal'] = 0.0
            return df_out
            
        # Calculate RSI
        delta = df_out['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        avg_gain = gain.ewm(alpha=1 / self.rsi_window, min_periods=self.rsi_window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.rsi_window, min_periods=self.rsi_window, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        df_out['rsi'] = 100.0 - (100.0 / (1.0 + rs))
        
        # Calculate Volume MA (Shifted by 1 to prevent current volume from inflating the baseline)
        df_out['vol_ma'] = df_out['Volume'].shift(1).rolling(window=self.vol_ma_window).mean()
        
        # Calculate ATR for position sizing (using Wilder's smoothing)
        high_low = df_out['High'] - df_out['Low']
        high_close = np.abs(df_out['High'] - df_out['Close'].shift())
        low_close = np.abs(df_out['Low'] - df_out['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df_out['atr'] = true_range.ewm(alpha=1/14, adjust=False).mean()
        
        # Generate Signals
        df_out['Signal'] = 0.0
        
        valid_mask = df_out['rsi'].notna() & df_out['vol_ma'].notna()
        
        buy_condition = (df_out['rsi'] < self.oversold) & (df_out['Volume'] > df_out['vol_ma'] * self.vol_multiplier)
        sell_condition = (df_out['rsi'] > self.overbought) & (df_out['Volume'] > df_out['vol_ma'] * self.vol_multiplier)
        
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
