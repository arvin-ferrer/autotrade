with open("web/static/script.js", "r") as f:
    content = f.read()

# Fix initializeCharts allocationChart
content = content.replace("labels: ['Cash PHP', 'BTC Position']", "labels: ['Cash PHP', 'Crypto Position']")

# Fix trade log btcSize
content = content.replace("const btcSize = `${t.size.toFixed(6)} BTC`;", "const btcSize = `${t.size.toFixed(6)} ${t.symbol ? t.symbol.split('/')[0] : ''}`;")

with open("web/static/script.js", "w") as f:
    f.write(content)
