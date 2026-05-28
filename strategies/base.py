from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd

class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    """
    def __init__(self, name: str, params: Optional[dict] = None):
        """
        Initialize the strategy.
        
        Args:
            name: Name of the strategy.
            params: Dictionary of strategy parameters.
        """
        self.name = name
        self.params = params or {}
        
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on the input price data.
        
        Args:
            df: A pandas DataFrame containing price data with a DatetimeIndex
                and columns: 'Open', 'High', 'Low', 'Close', 'Volume'.
                
        Returns:
            A pandas DataFrame containing indicator columns and a 'Signal'
            column (1.0 = Buy, -1.0 = Sell, 0.0 = Hold/Neutral).
        """
        pass
