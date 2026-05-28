import sqlite3
import json

conn = sqlite3.connect("live_trading.db")
holdings = {"BTC/USDT": 0.05, "ETH/USDT": 2.5}
conn.execute("UPDATE portfolio SET holdings_json = ? WHERE id = 1", (json.dumps(holdings),))
conn.commit()
conn.close()
