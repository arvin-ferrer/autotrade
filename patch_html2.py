with open("web/templates/index.html", "r") as f:
    content = f.read()

content = content.replace("BTC Algo Trader", "Crypto Algo Trader")
content = content.replace("Monitoring BTC/USDT paper-trading session in Philippine Time (PHT)", "Monitoring multi-coin paper-trading session in Philippine Time (PHT)")
content = content.replace("Available PHP to buy BTC", "Available PHP to buy crypto")

with open("web/templates/index.html", "w") as f:
    f.write(content)
