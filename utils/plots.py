import os
from typing import List
import matplotlib
# Set non-interactive backend for server/CLI environments
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

def render_ascii_price_chart(df: pd.DataFrame, limit: int = 20) -> None:
    """
    Renders a simple terminal trend chart of the closing prices for the last N rows.
    
    Args:
        df: Price DataFrame with Close column.
        limit: Number of recent rows to render.
    """
    recent = df.tail(limit)
    close_vals = recent['Close'].tolist()
    dates = [d.strftime('%Y-%m-%d') for d in recent.index]
    
    min_val = min(close_vals)
    max_val = max(close_vals)
    val_range = max_val - min_val if max_val != min_val else 1.0
    
    print(f"\n--- Terminal Trend Chart (Last {limit} candles) ---")
    for date, val in zip(dates, close_vals):
        # Scale price to a bar of 0-35 characters
        bar_len = int((val - min_val) / val_range * 35)
        bar = "█" * bar_len + "░" * (35 - bar_len)
        print(f"{date} | {val:,.2f} | {bar}")
    print("-" * 65 + "\n")

def plot_equity_curve(
    history_df: pd.DataFrame, 
    trades: List[dict], 
    output_filename: str = 'equity_curve.png'
) -> None:
    """
    Generates a high-quality dual-panel matplotlib chart showing:
    - Subplot 1: Price curve with buy/sell trade markers.
    - Subplot 2: Portfolio total equity curve.
    
    Saves the output as a PNG file.
    
    Args:
        history_df: Daily portfolio history DataFrame from the backtester.
        trades: List of trade dictionaries.
        output_filename: Filepath to save the PNG image.
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    # 1. Plot Close Price
    ax1.plot(history_df.index, history_df['Close'], label='BTC/USDT Close Price', color='grey', alpha=0.7, linewidth=1.5)
    
    # Annotate Trades on ax1
    buy_dates = []
    buy_prices = []
    sell_dates = []
    sell_prices = []
    
    for t in trades:
        # Check if dates exist in index
        entry_dt = pd.to_datetime(t['entry_date'], utc=True)
        exit_dt = pd.to_datetime(t['exit_date'], utc=True)
        
        buy_dates.append(entry_dt)
        buy_prices.append(t['entry_price'])
        sell_dates.append(exit_dt)
        sell_prices.append(t['exit_price'])
        
    if buy_dates:
        ax1.scatter(buy_dates, buy_prices, label='BUY Signal', color='green', marker='^', s=100, zorder=5)
    if sell_dates:
        ax1.scatter(sell_dates, sell_prices, label='SELL Signal', color='red', marker='v', s=100, zorder=5)
        
    ax1.set_title("BTC/USDT Price & Trade Signals", fontsize=14, fontweight='bold')
    ax1.set_ylabel("Price (USDT)", fontsize=12)
    ax1.grid(True, linestyle='--', alpha=0.5)
    ax1.legend(loc='upper left')
    
    # 2. Plot Equity Curve
    ax2.plot(history_df.index, history_df['Total_Value'], label='Portfolio Equity Value', color='blue', linewidth=2.0)
    
    # Optional: Plot Buy & Hold equity curve comparison
    initial_close = history_df['Close'].iloc[0]
    initial_val = history_df['Total_Value'].iloc[0]
    bh_equity = (history_df['Close'] / initial_close) * initial_val
    ax2.plot(history_df.index, bh_equity, label='Buy & Hold Equity', color='orange', linestyle='--', alpha=0.7)
    
    ax2.set_title("Portfolio Equity Growth (vs. Buy & Hold)", fontsize=14, fontweight='bold')
    ax2.set_ylabel("Portfolio Value (USDT)", fontsize=12)
    ax2.set_xlabel("Date", fontsize=12)
    ax2.grid(True, linestyle='--', alpha=0.5)
    ax2.legend(loc='upper left')
    
    plt.tight_layout()
    plt.savefig(output_filename, dpi=150)
    plt.close()
    print(f"Saved performance chart to: {output_filename}")
