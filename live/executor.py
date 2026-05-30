import json
import urllib.request
import pandas as pd
from typing import Optional
from live.db import get_open_trade, open_trade, close_trade, get_portfolio, update_portfolio, get_pht_now
import threading

portfolio_lock = threading.Lock()

def send_discord_alert(webhook_url: Optional[str], title: str, description: str, color: int, fields: list) -> None:
    """
    Sends a rich embed notification to Discord via a Webhook URL.
    """
    if not webhook_url:
        return
        
    payload = {
        "username": "Crypto Trading Bot",
        "avatar_url": "https://i.imgur.com/4E7t23q.png",  # Standard bot avatar
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields,
                "footer": {
                    "text": f"System Alert • {get_pht_now()}"
                }
            }
        ]
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=data,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0'
            }
        )
        with urllib.request.urlopen(req) as response:
            if response.status not in [200, 204]:
                print(f"[Discord] Unexpected response status: {response.status}")
    except Exception as e:
        print(f"[Discord Error] Failed to send alert: {e}")

def check_risk_limits(
    symbol: str,
    current_price: float,
    fee_rate: float,
    php_usd_rate: float,
    stop_loss_pct: Optional[float],
    take_profit_pct: Optional[float],
    discord_webhook_url: Optional[str]
) -> None:
    """
    Evaluates real-time stop-loss/take-profit triggers on every tick.
    Processes emergency exits in the SQLite database and sends Discord notifications.
    """
    with portfolio_lock:
        cash_php, holdings = get_portfolio()
        open_t = get_open_trade(symbol)
        asset_holding = holdings.get(symbol, 0.0)
    
    if open_t is not None and asset_holding > 0.0:
        entry_price = float(open_t['entry_price_usd'])
        risk_triggered = False
        risk_reason = None
        exit_trigger_price = current_price
        
        # Check stop loss
        if stop_loss_pct is not None:
            sl_threshold = entry_price * (1.0 - stop_loss_pct)
            if current_price <= sl_threshold:
                risk_triggered = True
                risk_reason = "STOP LOSS"
                exit_trigger_price = sl_threshold
                
        # Check take profit
        if not risk_triggered and take_profit_pct is not None:
            tp_threshold = entry_price * (1.0 + take_profit_pct)
            if current_price >= tp_threshold:
                risk_triggered = True
                risk_reason = "TAKE PROFIT"
                exit_trigger_price = tp_threshold
                
        if risk_triggered:
            # Execute Risk Sell Order (Simulate slippage by filling at current tick price)
            sell_price_usd = current_price
            sell_price_php = sell_price_usd * php_usd_rate
            
            sell_value_usd = asset_holding * sell_price_usd
            fee_usd = sell_value_usd * fee_rate
            net_cash_usd = sell_value_usd - fee_usd
            net_cash_php = net_cash_usd * php_usd_rate
            fee_php = fee_usd * php_usd_rate
            
            entry_cost_usd = open_t['size'] * open_t['entry_price_usd']
            profit_usd = net_cash_usd - entry_cost_usd
            profit_php = profit_usd * php_usd_rate
            profit_pct = (profit_usd / entry_cost_usd) * 100.0 if entry_cost_usd > 0 else 0.0
            
            # Update DB
            holdings[symbol] = 0.0
            new_cash_php = cash_php + net_cash_php
            update_portfolio(cash_php=new_cash_php, holdings=holdings)
            close_trade(
                trade_id=open_t['id'],
                exit_price_usd=sell_price_usd,
                exit_price_php=sell_price_php,
                fee_usd=fee_usd,
                fee_php=fee_php,
                profit_usd=profit_usd,
                profit_php=profit_php
            )
            
            log_msg = (
                f"🚨 [{risk_reason} TRIGGERED] Executed Trade #{open_t['id']}\n"
                f"Asset:          {symbol}\n"
                f"Entry Price:    ${entry_price:,.2f} USD (₱{entry_price * php_usd_rate:,.2f} PHP)\n"
                f"Exit Price:     ${sell_price_usd:,.2f} USD (₱{sell_price_php:,.2f} PHP)\n"
                f"Net Cash Recv:  ₱{net_cash_php:,.2f} PHP\n"
                f"Total Fee:      ₱{fee_php:,.2f} PHP\n"
                f"Trade Profit:   ₱{profit_php:+,.2f} PHP ({profit_pct:+.2f}%)\n"
                f"New Portfolio:  ₱{new_cash_php:,.2f} PHP cash, 0.00 {symbol}"
            )
            print(log_msg)
            
            # Send Discord Alert
            fields = [
                {"name": "Trigger Reason", "value": f"🚨 {risk_reason}", "inline": True},
                {"name": "Exit Price (PHP)", "value": f"₱{sell_price_php:,.2f} PHP", "inline": True},
                {"name": "Exit Price (USD)", "value": f"${sell_price_usd:,.2f} USD", "inline": True},
                {"name": "Trade Profit", "value": f"₱{profit_php:+,.2f} PHP ({profit_pct:+.2f}%)", "inline": False},
                {"name": "Portfolio State", "value": f"₱{new_cash_php:,.2f} Cash • 0.00 {symbol}", "inline": False}
            ]
            
            alert_color = 15158332 if risk_reason == "STOP LOSS" else 15844367
            send_discord_alert(
                webhook_url=discord_webhook_url,
                title=f"🛑 {risk_reason} TRIGGERED (Trade #{open_t['id']})",
                description=f"Risk threshold breached. Position auto-liquidated on live tick.",
                color=alert_color,
                fields=fields
            )
            return

def execute_live_signal(
    df: pd.DataFrame,
    symbol: str = 'BTC/USDT',
    fee_rate: float = 0.001,
    php_usd_rate: float = 58.5,
    stop_loss_pct: Optional[float] = None,
    discord_webhook_url: Optional[str] = None
) -> None:
    """
    Evaluates the latest signal from the DataFrame on candle close.
    Processes entries or exits in the SQLite database and sends Discord notifications.
    """
    if df.empty:
        return
        
    last_row = df.iloc[-1]
    signal = float(last_row.get('Signal', 0.0))
    price_usd = float(last_row['Close'])
    price_php = price_usd * php_usd_rate
    
    with portfolio_lock:
        cash_php, holdings = get_portfolio()
        open_t = get_open_trade(symbol)
        asset_holding = holdings.get(symbol, 0.0)
    
    # Check for standard strategy Signals
    if signal == 1.0:
        if open_t is not None:
            return
            
        if cash_php <= 0.0:
            print(f"[{get_pht_now()}] BUY signal generated for {symbol}, but cash is ₱0.00. No action taken.")
            return
            
        # Execute BUY Order
        cash_usd = cash_php / php_usd_rate
        
        if stop_loss_pct is not None and stop_loss_pct > 0:
            target_size = (cash_usd * 0.02) / (price_usd * stop_loss_pct)
        else:
            target_size = (cash_usd * 0.20) / price_usd
            
        max_size = cash_usd / (price_usd * (1.0 + fee_rate))
        buy_size = min(target_size, max_size)
        
        if buy_size <= 0:
            return
            
        buy_value_usd = buy_size * price_usd
        fee_usd = buy_value_usd * fee_rate
        total_cost_usd = buy_value_usd + fee_usd
        total_cost_php = total_cost_usd * php_usd_rate
        fee_php = fee_usd * php_usd_rate
        
        new_cash_php = max(0.0, cash_php - total_cost_php)
        holdings[symbol] = holdings.get(symbol, 0.0) + buy_size
        
        update_portfolio(cash_php=new_cash_php, holdings=holdings)
        trade_id = open_trade(
            symbol=symbol,
            entry_price_usd=price_usd,
            entry_price_php=price_php,
            size=buy_size,
            fee_usd=fee_usd,
            fee_php=fee_php
        )
        
        log_msg = (
            f"🛒 [BUY ORDER] Executed Trade #{trade_id}\n"
            f"Asset:          {symbol}\n"
            f"Price:          ${price_usd:,.2f} USD (₱{price_php:,.2f} PHP)\n"
            f"Size:           {buy_size:.6f} {symbol}\n"
            f"Fee:            ₱{fee_php:,.2f} PHP\n"
            f"New Portfolio:  ₱{new_cash_php:,.2f} PHP cash, {holdings[symbol]:.6f} {symbol}"
        )
        print(log_msg)
        
        fields = [
            {"name": "Price (PHP)", "value": f"₱{price_php:,.2f} PHP", "inline": True},
            {"name": "Price (USD)", "value": f"${price_usd:,.2f} USD", "inline": True},
            {"name": "Size", "value": f"{buy_size:.6f} {symbol}", "inline": True},
            {"name": "Fee (PHP)", "value": f"₱{fee_php:,.2f} PHP", "inline": True},
            {"name": "Portfolio State", "value": f"₱{new_cash_php:,.2f} Cash • {holdings[symbol]:.6f} {symbol}", "inline": False}
        ]
        send_discord_alert(
            webhook_url=discord_webhook_url,
            title=f"🟢 BUY ORDER EXECUTED (Trade #{trade_id})",
            description=f"Automated paper order triggered on live candle close.",
            color=3066993,
            fields=fields
        )
 
    elif signal == -1.0:
        if open_t is None:
            return
            
        if asset_holding <= 0.0:
            print(f"[{get_pht_now()}] SELL signal generated for {symbol}, but holdings are 0. No action taken.")
            return
            
        # Execute SELL Order
        sell_value_usd = asset_holding * price_usd
        fee_usd = sell_value_usd * fee_rate
        net_cash_usd = sell_value_usd - fee_usd
        net_cash_php = net_cash_usd * php_usd_rate
        fee_php = fee_usd * php_usd_rate
        
        entry_cost_usd = open_t['size'] * open_t['entry_price_usd']
        profit_usd = net_cash_usd - entry_cost_usd
        profit_php = profit_usd * php_usd_rate
        profit_pct = (profit_usd / entry_cost_usd) * 100.0 if entry_cost_usd > 0 else 0.0
        
        holdings[symbol] = 0.0
        new_cash_php = cash_php + net_cash_php
        update_portfolio(cash_php=new_cash_php, holdings=holdings)
        close_trade(
            trade_id=open_t['id'],
            exit_price_usd=price_usd,
            exit_price_php=price_php,
            fee_usd=fee_usd,
            fee_php=fee_php,
            profit_usd=profit_usd,
            profit_php=profit_php
        )
        
        log_msg = (
            f"🏁 [SELL ORDER] Executed Trade #{open_t['id']}\n"
            f"Asset:          {symbol}\n"
            f"Price:          ${price_usd:,.2f} USD (₱{price_php:,.2f} PHP)\n"
            f"Net Cash Recv:  ₱{net_cash_php:,.2f} PHP\n"
            f"Total Fee:      ₱{fee_php:,.2f} PHP\n"
            f"Trade Profit:   ₱{profit_php:+,.2f} PHP ({profit_pct:+.2f}%)\n"
            f"New Portfolio:  ₱{new_cash_php:,.2f} PHP cash, 0.00 {symbol}"
        )
        print(log_msg)
        
        fields = [
            {"name": "Price (PHP)", "value": f"₱{price_php:,.2f} PHP", "inline": True},
            {"name": "Price (USD)", "value": f"${price_usd:,.2f} USD", "inline": True},
            {"name": "Trade Profit", "value": f"₱{profit_php:+,.2f} PHP ({profit_pct:+.2f}%)", "inline": True},
            {"name": "Fee (PHP)", "value": f"₱{fee_php:,.2f} PHP", "inline": True},
            {"name": "Portfolio State", "value": f"₱{new_cash_php:,.2f} Cash • 0.00 {symbol}", "inline": False}
        ]
        
        alert_color = 3066993 if profit_usd >= 0 else 15158332
        send_discord_alert(
            webhook_url=discord_webhook_url,
            title=f"🔴 SELL ORDER EXECUTED (Trade #{open_t['id']})",
            description=f"Automated paper order closed on live candle close.",
            color=alert_color,
            fields=fields
        )
