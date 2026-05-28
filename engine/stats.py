import numpy as np
import pandas as pd
from typing import List, Dict, Any

def calculate_performance_metrics(
    history_df: pd.DataFrame,
    trades: List[Dict[str, Any]],
    initial_capital: float
) -> Dict[str, Any]:
    """
    Calculate portfolio performance and risk metrics.
    
    Args:
        history_df: A pandas DataFrame containing daily equity history with columns:
            ['Cash', 'Holdings', 'Asset_Value', 'Total_Value', 'Close']
        trades: A list of trade dictionaries.
        initial_capital: The starting capital of the backtest.
        
    Returns:
        A dictionary containing computed performance metrics:
        - initial_value: The starting capital.
        - final_value: The final total portfolio value.
        - total_return_pct: The overall return percentage of the portfolio.
        - annualized_return_pct: The compound annual growth rate (CAGR).
        - buy_and_hold_return_pct: The return from buying and holding the asset.
        - sharpe_ratio: The annualized Sharpe Ratio (assumes 0 risk-free rate).
        - max_drawdown_pct: The maximum drawdown percentage.
        - total_trades: The number of executed trades.
        - win_rate_pct: The percentage of profitable trades.
        - profit_factor: The ratio of gross profits to gross losses.
    """
    if history_df.empty:
        return {
            'initial_value': initial_capital,
            'final_value': initial_capital,
            'total_return_pct': 0.0,
            'annualized_return_pct': 0.0,
            'buy_and_hold_return_pct': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown_pct': 0.0,
            'total_trades': 0,
            'win_rate_pct': 0.0,
            'profit_factor': 0.0
        }
        
    initial_value = float(initial_capital)
    final_value = float(history_df['Total_Value'].iloc[-1])
    
    # 1. Total Return (%)
    total_return_pct = ((final_value - initial_value) / initial_value) * 100.0 if initial_value > 0.0 else 0.0
    
    # 2. Annualized Return (%)
    # Calculated based on the number of active trading days (rows) in the history DataFrame.
    # Crypto trades 24/7/365, so 1 year = 365 days.
    num_days = len(history_df)
    if num_days > 0 and initial_value > 0.0 and final_value > 0.0:
        years = num_days / 365.0
        # To avoid negative base exponentiation if final_value <= 0 (though portfolio shouldn't be negative)
        if final_value > 0.0:
            annualized_return_pct = ((final_value / initial_value) ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0
        else:
            annualized_return_pct = -100.0
    else:
        annualized_return_pct = 0.0
        
    # 3. Buy & Hold Return (%)
    # Compares the Close price at the end date against the Close price at the start date.
    buy_and_hold_return_pct = 0.0
    if 'Close' in history_df.columns and len(history_df) > 0:
        start_price = float(history_df['Close'].iloc[0])
        end_price = float(history_df['Close'].iloc[-1])
        buy_and_hold_return_pct = ((end_price - start_price) / start_price) * 100.0 if start_price > 0.0 else 0.0
        
    # 4. Sharpe Ratio (annualized)
    # Annualized daily Sharpe Ratio: (mean / std) * sqrt(365)
    daily_returns = history_df['Total_Value'].pct_change().dropna()
    if len(daily_returns) < 1:
        sharpe_ratio = 0.0
    else:
        mean_return = daily_returns.mean()
        std_return = daily_returns.std(ddof=1)
        if std_return == 0.0 or np.isnan(std_return):
            sharpe_ratio = 0.0
        else:
            sharpe_ratio = (mean_return / std_return) * np.sqrt(365.0)
            
    # 5. Maximum Drawdown (%)
    peaks = history_df['Total_Value'].cummax()
    # Replace peak values of 0 with NaN to avoid division-by-zero
    drawdowns = (history_df['Total_Value'] - peaks) / peaks.replace(0, np.nan)
    max_drawdown_pct = abs(drawdowns.min()) * 100.0
    if np.isnan(max_drawdown_pct):
        max_drawdown_pct = 0.0
        
    # 6. Trade metrics
    total_trades = len(trades)
    
    if total_trades == 0:
        win_rate_pct = 0.0
        profit_factor = 0.0
    else:
        winning_trades = sum(1 for t in trades if t['profit'] > 0.0)
        win_rate_pct = (winning_trades / total_trades) * 100.0
        
        gross_profit = sum(t['profit'] for t in trades if t['profit'] > 0.0)
        gross_loss = sum(abs(t['profit']) for t in trades if t['profit'] < 0.0)
        
        if gross_loss == 0.0:
            profit_factor = float('inf') if gross_profit > 0.0 else 0.0
        else:
            profit_factor = float(gross_profit / gross_loss)
            
    return {
        'initial_value': initial_value,
        'final_value': final_value,
        'total_return_pct': total_return_pct,
        'annualized_return_pct': annualized_return_pct,
        'buy_and_hold_return_pct': buy_and_hold_return_pct,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown_pct': max_drawdown_pct,
        'total_trades': total_trades,
        'win_rate_pct': win_rate_pct,
        'profit_factor': profit_factor
    }
