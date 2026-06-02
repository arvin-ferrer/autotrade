import json
import urllib.request
import pandas as pd
from datetime import datetime, timezone
from typing import Optional
from live.db import (
    get_open_trade, open_trade, close_trade, get_portfolio, update_portfolio, get_pht_now,
    get_open_position, open_position, update_position_stop,
    update_position_funding, close_position
)
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


# ============================================================================
# V2 BREAKOUT EXECUTOR — Bidirectional LONG/SHORT with ATR trailing stops
# ============================================================================

def execute_v2_signal(
    df: pd.DataFrame,
    symbol: str,
    last_total_equity: float,
    num_symbols: int,
    fee_rate: float = 0.0005,
    funding_rate: float = 0.0001,
    stop_mult: float = 2.0,
    tp_mult: float = 10.0,
    risk_pct: float = 0.01,
    max_leverage: float = 2.0,
    php_usd_rate: float = 58.5,
    discord_webhook_url: Optional[str] = None
) -> None:
    """
    V2 breakout executor: processes candle-close signals for bidirectional
    LONG/SHORT positions with ATR-based risk management.
    
    Mirrors the backtest engine in scripts/breakout_v2_backtest.py lines 146-249.
    Signal at bar T-1 → execution at bar T open (which in live = current candle close).
    """
    if df.empty or len(df) < 2:
        return

    last_row = df.iloc[-1]

    # The candle that JUST closed is last_row. Its signal is what we trade on.
    # Its Close price is the exact same as the next candle's Open price.
    prev_signal = float(last_row.get('Signal', 0.0))
    prev_atr = float(last_row.get('atr', 0.0))
    
    curr_close = float(last_row['Close'])
    
    if pd.isna(prev_atr) or prev_atr <= 0:
        return

    with portfolio_lock:
        pos = get_open_position(symbol)

        if pos is None:
            # FLAT → check for entry signals
            if prev_signal == 1.0:
                # === OPEN LONG ===
                exec_price = curr_close  # Live: current candle close = next bar open proxy
                risk_amount = last_total_equity * risk_pct
                qty = risk_amount / (stop_mult * prev_atr)
                max_qty = (last_total_equity * max_leverage / num_symbols) / exec_price
                qty = min(qty, max_qty)

                if qty <= 0:
                    return

                notional = qty * exec_price
                fee = notional * fee_rate
                trailing_stop = exec_price - (stop_mult * prev_atr)
                take_profit = exec_price + (tp_mult * prev_atr)

                pos_id = open_position(
                    symbol=symbol,
                    direction='LONG',
                    entry_price=exec_price,
                    qty=qty,
                    trailing_stop=trailing_stop,
                    take_profit=take_profit,
                    extreme_close=curr_close,
                    fee=fee
                )

                log_msg = (
                    f"🟢 [V2 LONG ENTRY] Position #{pos_id}\n"
                    f"Asset:          {symbol}\n"
                    f"Price:          ${exec_price:,.4f} USD (₱{exec_price * php_usd_rate:,.2f} PHP)\n"
                    f"Qty:            {qty:.6f}\n"
                    f"Notional:       ${notional:,.2f} USD\n"
                    f"ATR (prev):     ${prev_atr:,.4f}\n"
                    f"Trailing Stop:  ${trailing_stop:,.4f}\n"
                    f"Take Profit:    ${take_profit:,.4f}\n"
                    f"Fee:            ${fee:,.4f} USD"
                )
                print(log_msg)

                fields = [
                    {"name": "Direction", "value": "📈 LONG", "inline": True},
                    {"name": "Price (USD)", "value": f"${exec_price:,.4f}", "inline": True},
                    {"name": "Qty", "value": f"{qty:.6f}", "inline": True},
                    {"name": "ATR", "value": f"${prev_atr:,.4f}", "inline": True},
                    {"name": "Trailing Stop", "value": f"${trailing_stop:,.4f}", "inline": True},
                    {"name": "Take Profit", "value": f"${take_profit:,.4f}", "inline": True},
                    {"name": "Notional", "value": f"${notional:,.2f} USD", "inline": False},
                    {"name": "Funding Rate", "value": f"{funding_rate*100:.3f}% per 8h", "inline": True},
                ]
                send_discord_alert(
                    webhook_url=discord_webhook_url,
                    title=f"🟢 V2 LONG ENTRY (Position #{pos_id})",
                    description=f"Breakout signal triggered LONG entry on {symbol}.",
                    color=3066993,
                    fields=fields
                )

            elif prev_signal == -1.0:
                # === OPEN SHORT ===
                exec_price = curr_close
                risk_amount = last_total_equity * risk_pct
                qty = risk_amount / (stop_mult * prev_atr)
                max_qty = (last_total_equity * max_leverage / num_symbols) / exec_price
                qty = min(qty, max_qty)

                if qty <= 0:
                    return

                notional = qty * exec_price
                fee = notional * fee_rate
                trailing_stop = exec_price + (stop_mult * prev_atr)
                take_profit = exec_price - (tp_mult * prev_atr)

                pos_id = open_position(
                    symbol=symbol,
                    direction='SHORT',
                    entry_price=exec_price,
                    qty=qty,
                    trailing_stop=trailing_stop,
                    take_profit=take_profit,
                    extreme_close=curr_close,
                    fee=fee
                )

                log_msg = (
                    f"🔴 [V2 SHORT ENTRY] Position #{pos_id}\n"
                    f"Asset:          {symbol}\n"
                    f"Price:          ${exec_price:,.4f} USD (₱{exec_price * php_usd_rate:,.2f} PHP)\n"
                    f"Qty:            {qty:.6f}\n"
                    f"Notional:       ${notional:,.2f} USD\n"
                    f"ATR (prev):     ${prev_atr:,.4f}\n"
                    f"Trailing Stop:  ${trailing_stop:,.4f}\n"
                    f"Take Profit:    ${take_profit:,.4f}\n"
                    f"Fee:            ${fee:,.4f} USD"
                )
                print(log_msg)

                fields = [
                    {"name": "Direction", "value": "📉 SHORT", "inline": True},
                    {"name": "Price (USD)", "value": f"${exec_price:,.4f}", "inline": True},
                    {"name": "Qty", "value": f"{qty:.6f}", "inline": True},
                    {"name": "ATR", "value": f"${prev_atr:,.4f}", "inline": True},
                    {"name": "Trailing Stop", "value": f"${trailing_stop:,.4f}", "inline": True},
                    {"name": "Take Profit", "value": f"${take_profit:,.4f}", "inline": True},
                    {"name": "Notional", "value": f"${notional:,.2f} USD", "inline": False},
                    {"name": "Funding Rate", "value": f"{funding_rate*100:.3f}% per 8h", "inline": True},
                ]
                send_discord_alert(
                    webhook_url=discord_webhook_url,
                    title=f"🔴 V2 SHORT ENTRY (Position #{pos_id})",
                    description=f"Breakout signal triggered SHORT entry on {symbol}.",
                    color=15158332,
                    fields=fields
                )

        elif pos['direction'] == 'LONG':
            if prev_signal == -1.0:
                # === CLOSE LONG on signal reversal ===
                exit_price = curr_close
                proceeds = pos['qty'] * exit_price
                exit_fee = proceeds * fee_rate
                pnl = proceeds - exit_fee - (pos['qty'] * pos['entry_price_usd'])
    
                close_position(
                    position_id=pos['id'],
                    exit_price=exit_price,
                    profit=pnl,
                    exit_fee=exit_fee
                )
    
                pnl_pct = (pnl / (pos['qty'] * pos['entry_price_usd'])) * 100.0
                log_msg = (
                    f"🏁 [V2 LONG EXIT — Signal Reversal] Position #{pos['id']}\n"
                    f"Asset:          {symbol}\n"
                    f"Direction:      LONG\n"
                    f"Entry:          ${pos['entry_price_usd']:,.4f}\n"
                    f"Exit:           ${exit_price:,.4f}\n"
                    f"P&L:            ${pnl:+,.4f} ({pnl_pct:+.2f}%)\n"
                    f"Funding Paid:   ${pos['total_funding']:,.4f}"
                )
                print(log_msg)
    
                fields = [
                    {"name": "Direction", "value": "📈 LONG → CLOSED", "inline": True},
                    {"name": "Exit Reason", "value": "Signal Reversal", "inline": True},
                    {"name": "Entry", "value": f"${pos['entry_price_usd']:,.4f}", "inline": True},
                    {"name": "Exit", "value": f"${exit_price:,.4f}", "inline": True},
                    {"name": "P&L", "value": f"${pnl:+,.4f} ({pnl_pct:+.2f}%)", "inline": True},
                    {"name": "Total Funding", "value": f"${pos['total_funding']:,.4f}", "inline": True},
                ]
                alert_color = 3066993 if pnl >= 0 else 15158332
                send_discord_alert(
                    webhook_url=discord_webhook_url,
                    title=f"🏁 V2 LONG CLOSED (Position #{pos['id']})",
                    description=f"Signal reversal closed LONG on {symbol}.",
                    color=alert_color,
                    fields=fields
                )
            else:
                # === RATCHET TRAILING STOP ===
                new_extreme = max(pos['extreme_close'], curr_close)
                new_ts = max(pos['trailing_stop_price'], new_extreme - (stop_mult * prev_atr))
                if new_extreme != pos['extreme_close'] or new_ts != pos['trailing_stop_price']:
                    update_position_stop(pos['id'], new_ts, new_extreme)

        elif pos['direction'] == 'SHORT':
            if prev_signal == 1.0:
                # === CLOSE SHORT on signal reversal ===
                exit_price = curr_close
                cost = pos['qty'] * exit_price
                exit_fee = cost * fee_rate
                pnl = (pos['entry_price_usd'] - exit_price) * pos['qty'] - exit_fee
    
                close_position(
                    position_id=pos['id'],
                    exit_price=exit_price,
                    profit=pnl,
                    exit_fee=exit_fee
                )
    
                pnl_pct = (pnl / (pos['qty'] * pos['entry_price_usd'])) * 100.0
                log_msg = (
                    f"🏁 [V2 SHORT EXIT — Signal Reversal] Position #{pos['id']}\n"
                    f"Asset:          {symbol}\n"
                    f"Direction:      SHORT\n"
                    f"Entry:          ${pos['entry_price_usd']:,.4f}\n"
                    f"Exit:           ${exit_price:,.4f}\n"
                    f"P&L:            ${pnl:+,.4f} ({pnl_pct:+.2f}%)\n"
                    f"Funding Recv:   ${pos['total_funding']:,.4f}"
                )
                print(log_msg)
    
                fields = [
                    {"name": "Direction", "value": "📉 SHORT → CLOSED", "inline": True},
                    {"name": "Exit Reason", "value": "Signal Reversal", "inline": True},
                    {"name": "Entry", "value": f"${pos['entry_price_usd']:,.4f}", "inline": True},
                    {"name": "Exit", "value": f"${exit_price:,.4f}", "inline": True},
                    {"name": "P&L", "value": f"${pnl:+,.4f} ({pnl_pct:+.2f}%)", "inline": True},
                    {"name": "Total Funding", "value": f"${pos['total_funding']:,.4f}", "inline": True},
                ]
                alert_color = 3066993 if pnl >= 0 else 15158332
                send_discord_alert(
                    webhook_url=discord_webhook_url,
                    title=f"🏁 V2 SHORT CLOSED (Position #{pos['id']})",
                    description=f"Signal reversal closed SHORT on {symbol}.",
                    color=alert_color,
                    fields=fields
                )
            else:
                # === RATCHET TRAILING STOP ===
                new_extreme = min(pos['extreme_close'], curr_close)
                new_ts = min(pos['trailing_stop_price'], new_extreme + (stop_mult * prev_atr))
                if new_extreme != pos['extreme_close'] or new_ts != pos['trailing_stop_price']:
                    update_position_stop(pos['id'], new_ts, new_extreme)


def check_v2_risk(
    symbol: str,
    tick_price: float,
    curr_atr: float,
    fee_rate: float = 0.0005,
    funding_rate: float = 0.0001,
    stop_mult: float = 2.0,
    php_usd_rate: float = 58.5,
    discord_webhook_url: Optional[str] = None
) -> None:
    """
    V2 real-time risk check on every tick:
    - ATR trailing stop ratcheting
    - Take-profit evaluation
    - Funding rate application at hours 0, 8, 16 UTC
    
    Mirrors the backtest engine in scripts/breakout_v2_backtest.py lines 187-249.
    """
    with portfolio_lock:
        pos = get_open_position(symbol)

    if pos is None:
        return

    direction = pos['direction']
    trailing_stop = pos['trailing_stop_price']
    take_profit = pos['take_profit_price']
    extreme = pos['extreme_close']
    qty = pos['qty']
    entry_price = pos['entry_price_usd']
    pos_id = pos['id']

    exit_triggered = False
    exit_reason = ""
    exit_price = tick_price

    if direction == 'LONG':
        # Check trailing stop
        if tick_price <= trailing_stop:
            exit_triggered = True
            exit_reason = "TRAILING STOP"
            exit_price = trailing_stop  # Fill at stop level
        # Check take profit
        elif tick_price >= take_profit:
            exit_triggered = True
            exit_reason = "TAKE PROFIT"
            exit_price = take_profit

    elif direction == 'SHORT':
        # Check trailing stop
        if tick_price >= trailing_stop:
            exit_triggered = True
            exit_reason = "TRAILING STOP"
            exit_price = trailing_stop
        # Check take profit
        elif tick_price <= take_profit:
            exit_triggered = True
            exit_reason = "TAKE PROFIT"
            exit_price = take_profit

    if exit_triggered:
        with portfolio_lock:
            if direction == 'LONG':
                proceeds = qty * exit_price
                exit_fee = proceeds * fee_rate
                pnl = proceeds - exit_fee - (qty * entry_price)
            else:  # SHORT
                cost = qty * exit_price
                exit_fee = cost * fee_rate
                pnl = (entry_price - exit_price) * qty - exit_fee

            close_position(
                position_id=pos_id,
                exit_price=exit_price,
                profit=pnl,
                exit_fee=exit_fee
            )

        pnl_pct = (pnl / (qty * entry_price)) * 100.0 if entry_price > 0 else 0.0
        log_msg = (
            f"🚨 [V2 {exit_reason}] Position #{pos_id}\n"
            f"Asset:          {symbol}\n"
            f"Direction:      {direction}\n"
            f"Entry:          ${entry_price:,.4f}\n"
            f"Exit:           ${exit_price:,.4f}\n"
            f"P&L:            ${pnl:+,.4f} ({pnl_pct:+.2f}%)\n"
            f"Funding Total:  ${pos['total_funding']:,.4f}"
        )
        print(log_msg)

        fields = [
            {"name": "Direction", "value": f"{'📈' if direction == 'LONG' else '📉'} {direction}", "inline": True},
            {"name": "Exit Reason", "value": f"🚨 {exit_reason}", "inline": True},
            {"name": "Entry", "value": f"${entry_price:,.4f}", "inline": True},
            {"name": "Exit", "value": f"${exit_price:,.4f}", "inline": True},
            {"name": "P&L", "value": f"${pnl:+,.4f} ({pnl_pct:+.2f}%)", "inline": True},
            {"name": "ATR Stop", "value": f"${trailing_stop:,.4f}", "inline": True},
            {"name": "Total Funding", "value": f"${pos['total_funding']:,.4f}", "inline": False},
        ]
        alert_color = 15158332 if exit_reason == "TRAILING STOP" else 15844367
        send_discord_alert(
            webhook_url=discord_webhook_url,
            title=f"🛑 V2 {exit_reason} ({direction} Position #{pos_id})",
            description=f"ATR-based {exit_reason.lower()} triggered on {symbol}.",
            color=alert_color,
            fields=fields
        )
        return

    # Funding rate application at UTC hours 0, 8, 16
    now_utc = datetime.now(timezone.utc)
    if now_utc.hour in [0, 8, 16] and now_utc.minute == 0:
        funding_amount = qty * tick_price * funding_rate
        if direction == 'LONG':
            # LONG pays funding
            funding_amount = -funding_amount
        # else SHORT receives (positive)
        
        with portfolio_lock:
            update_position_funding(pos_id, funding_amount)
        
        print(
            f"💰 [V2 FUNDING] Position #{pos_id} {symbol} {direction}: "
            f"${funding_amount:+,.4f} (rate={funding_rate*100:.3f}%)"
        )

