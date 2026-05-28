import pandas as pd
from typing import Tuple, List, Dict, Any, Optional

class Backtester:
    """
    A class to simulate algorithmic trading on historical price data.
    Supports long-only position entry and exit with transaction fees and slippage.
    """
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        fee_rate: float = 0.001,
        slippage_rate: float = 0.0,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None
    ):
        """
        Initialize the Backtester.
        
        Args:
            initial_capital: The starting cash in the account (default: 10000.0).
            fee_rate: The transaction fee rate as a decimal (e.g., 0.001 for 0.1%).
            slippage_rate: The slippage rate as a decimal (e.g., 0.0005 for 0.05%).
            stop_loss_pct: Stop loss threshold as decimal percentage (e.g. 0.02 for 2%).
            take_profit_pct: Take profit threshold as decimal percentage (e.g. 0.05 for 5%).
        """
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def run(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Run the chronological backtest simulation.
        
        Args:
            df: A pandas DataFrame with a DatetimeIndex, a 'Close' price column,
                and a 'Signal' column (1.0 = Buy, -1.0 = Sell, 0.0 = Hold).
                
        Returns:
            A tuple containing:
            1. A history DataFrame of daily equity values with columns:
               ['Cash', 'Holdings', 'Asset_Value', 'Total_Value', 'Close']
            2. A list of trade dictionaries containing trade details.
        """
        # Handle empty DataFrame edge case
        if df.empty:
            history_df = pd.DataFrame(
                columns=['Cash', 'Holdings', 'Asset_Value', 'Total_Value', 'Close'],
                index=pd.to_datetime([], utc=True)
            )
            history_df.index.name = df.index.name or 'Timestamp'
            return history_df, []

        cash = float(self.initial_capital)
        holdings = 0.0
        trades: List[Dict[str, Any]] = []
        history_records: List[Dict[str, Any]] = []
        
        current_trade: Optional[Dict[str, Any]] = None
        
        for timestamp, row in df.iterrows():
            close_price = float(row['Close'])
            signal = float(row.get('Signal', 0.0))
            
            # Check for active position risk threshold triggers (Stop Loss / Take Profit)
            risk_exit = False
            exit_reason = 'Signal'
            exit_price = close_price
            
            if holdings > 0.0 and current_trade is not None:
                entry_price = current_trade['entry_price']
                
                # Check stop loss
                if self.stop_loss_pct is not None:
                    sl_price = entry_price * (1.0 - self.stop_loss_pct)
                    if close_price <= sl_price:
                        risk_exit = True
                        exit_reason = 'Stop Loss'
                        exit_price = sl_price
                
                # Check take profit
                if not risk_exit and self.take_profit_pct is not None:
                    tp_price = entry_price * (1.0 + self.take_profit_pct)
                    if close_price >= tp_price:
                        risk_exit = True
                        exit_reason = 'Take Profit'
                        exit_price = tp_price
            
            # Trigger exit if risk rules matched
            if risk_exit and holdings > 0.0:
                # Apply slippage (selling decreases price)
                exit_price = exit_price * (1.0 - self.slippage_rate)
                sale_amount = holdings * exit_price
                exit_fee = sale_amount * self.fee_rate
                cash_received = sale_amount - exit_fee
                cash = cash_received
                
                if current_trade is not None:
                    entry_fee = current_trade['entry_fee']
                    total_fee = entry_fee + exit_fee
                    cash_spent = current_trade['size'] * current_trade['entry_price'] + entry_fee
                    profit = cash - cash_spent
                    return_pct = (profit / cash_spent) * 100.0 if cash_spent > 0.0 else 0.0
                    
                    trades.append({
                        'entry_date': current_trade['entry_date'],
                        'exit_date': timestamp,
                        'entry_price': current_trade['entry_price'],
                        'exit_price': exit_price,
                        'size': current_trade['size'],
                        'profit': profit,
                        'return_pct': return_pct,
                        'fee': total_fee,
                        'exit_reason': exit_reason
                    })
                holdings = 0.0
                current_trade = None
                
            # Check for buy signal: Signal == 1.0 and no position is open
            elif signal == 1.0 and holdings == 0.0:
                # Apply slippage (buying increases price)
                entry_price = close_price * (1.0 + self.slippage_rate)
                size = cash / (entry_price * (1.0 + self.fee_rate))
                entry_fee = size * entry_price * self.fee_rate
                
                cash = 0.0
                holdings = size
                
                current_trade = {
                    'entry_date': timestamp,
                    'entry_price': entry_price,
                    'size': size,
                    'entry_fee': entry_fee
                }
                
            # Check for normal sell signal: Signal == -1.0 and position is open
            elif signal == -1.0 and holdings > 0.0:
                # Apply slippage (selling decreases price)
                exit_price = close_price * (1.0 - self.slippage_rate)
                sale_amount = holdings * exit_price
                exit_fee = sale_amount * self.fee_rate
                cash_received = sale_amount - exit_fee
                
                cash = cash_received
                
                # Close the trade and record metrics
                if current_trade is not None:
                    entry_fee = current_trade['entry_fee']
                    total_fee = entry_fee + exit_fee
                    cash_spent = current_trade['size'] * current_trade['entry_price'] + entry_fee
                    profit = cash - cash_spent
                    return_pct = (profit / cash_spent) * 100.0 if cash_spent > 0.0 else 0.0
                    
                    trades.append({
                        'entry_date': current_trade['entry_date'],
                        'exit_date': timestamp,
                        'entry_price': current_trade['entry_price'],
                        'exit_price': exit_price,
                        'size': current_trade['size'],
                        'profit': profit,
                        'return_pct': return_pct,
                        'fee': total_fee,
                        'exit_reason': 'Signal'
                    })
                    
                holdings = 0.0
                current_trade = None
            
            # Track daily equity metrics
            asset_value = holdings * close_price
            total_value = cash + asset_value
            
            history_records.append({
                'Cash': cash,
                'Holdings': holdings,
                'Asset_Value': asset_value,
                'Total_Value': total_value,
                'Close': close_price
            })
            
        # Create history DataFrame
        history_df = pd.DataFrame(history_records, index=df.index)
        
        # If there is an open position at the end of the simulation,
        # we close it at the final close price for the trade log (without altering the history)
        if current_trade is not None:
            last_timestamp = df.index[-1]
            last_close = float(df.iloc[-1]['Close'])
            exit_price = last_close * (1.0 - self.slippage_rate)
            sale_amount = holdings * exit_price
            exit_fee = sale_amount * self.fee_rate
            cash_received = sale_amount - exit_fee
            
            entry_fee = current_trade['entry_fee']
            total_fee = entry_fee + exit_fee
            cash_spent = current_trade['size'] * current_trade['entry_price'] + entry_fee
            profit = cash_received - cash_spent
            return_pct = (profit / cash_spent) * 100.0 if cash_spent > 0.0 else 0.0
            
            trades.append({
                'entry_date': current_trade['entry_date'],
                'exit_date': last_timestamp,
                'entry_price': current_trade['entry_price'],
                'exit_price': exit_price,
                'size': current_trade['size'],
                'profit': profit,
                'return_pct': return_pct,
                'fee': total_fee,
                'exit_reason': 'End of Data'
            })
            
        return history_df, trades
