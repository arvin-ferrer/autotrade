with open("web/static/script.js", "r") as f:
    content = f.read()

old_dom = """    // Price ticker
    document.getElementById("btc-price-val").innerText = `₱${m.btc_price_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;
    document.getElementById("btc-price-usd").innerText = `$${m.btc_price_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} USD`;

    // Portfolio metrics
    document.getElementById("total-val-php").innerText = `₱${m.total_value_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;
    document.getElementById("total-val-usd").innerText = `$${m.total_value_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} USD`;
    document.getElementById("cash-val-php").innerText = `₱${m.cash_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;
    document.getElementById("holdings-val-btc").innerText = `${m.btc_holdings.toFixed(6)} BTC`;
    document.getElementById("holdings-val-php").innerText = `Value: ₱${m.btc_value_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;"""

new_dom = """    // Price ticker (now Portfolio Value)
    document.getElementById("header-total-usd").innerText = `$${m.total_value_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} USD`;
    document.getElementById("header-active-assets").innerText = `${m.assets ? m.assets.length : 0} Active Asset${(m.assets && m.assets.length !== 1) ? 's' : ''}`;

    // Portfolio metrics
    document.getElementById("total-val-php").innerText = `₱${m.total_value_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;
    document.getElementById("total-val-usd").innerText = `$${m.total_value_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} USD`;
    document.getElementById("cash-val-php").innerText = `₱${m.cash_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;
    document.getElementById("assets-count-val").innerText = `${m.assets ? m.assets.length : 0} Asset${(m.assets && m.assets.length !== 1) ? 's' : ''}`;
    document.getElementById("assets-val-php").innerText = `Value: ₱${(m.total_assets_php || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;"""

content = content.replace(old_dom, new_dom)

old_banner = """    // Active Position alert banner logic
    const positionBanner = document.getElementById("position-banner");
    if (m.open_position && m.active_trade) {
        document.getElementById("banner-btc-size").innerText = m.btc_holdings.toFixed(6);
        document.getElementById("banner-entry-price").innerText = m.active_trade.entry_price_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        positionBanner.classList.remove("hidden");
    } else {
        positionBanner.classList.add("hidden");
    }"""

new_banner = """    // Active Position alert banner logic
    const positionBanner = document.getElementById("position-banner");
    if (m.open_position) {
        document.getElementById("banner-assets-count").innerText = m.assets ? m.assets.length : 0;
        positionBanner.classList.remove("hidden");
    } else {
        positionBanner.classList.add("hidden");
    }

    // Render Assets
    const assetsGrid = document.getElementById("assets-grid");
    if (m.assets && m.assets.length > 0) {
        assetsGrid.innerHTML = m.assets.map(a => `
            <div class="asset-card">
                <div class="asset-header">
                    <div class="asset-symbol">${a.symbol}</div>
                    <div class="asset-icon"><i class="${a.symbol.includes('BTC') ? 'fa-brands fa-bitcoin' : (a.symbol.includes('ETH') ? 'fa-brands fa-ethereum' : 'fa-solid fa-coins')}"></i></div>
                </div>
                <div class="asset-amount">${a.amount.toFixed(6)}</div>
                <div class="asset-value">₱${a.value_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                <div class="asset-price">
                    <span>Price</span>
                    <span class="price-val">$${a.price_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                </div>
            </div>
        `).join('');
    } else {
        assetsGrid.innerHTML = `<div class="text-secondary" style="grid-column: 1 / -1; text-align: center; padding: 2rem;">No active assets...</div>`;
    }"""

content = content.replace(old_banner, new_banner)

old_charts = """    // 1. Update Asset Allocation Doughnut Chart
    const cashVal = m.cash_php;
    const btcVal = m.btc_value_php;
    const totalVal = cashVal + btcVal;

    if (totalVal > 0) {
        const cashRatio = (cashVal / totalVal) * 100;
        const btcRatio = (btcVal / totalVal) * 100;
        allocationChart.data.datasets[0].data = [cashRatio, btcRatio];
        allocationChart.update();
    }"""

new_charts = """    // 1. Update Asset Allocation Doughnut Chart
    if (m.assets) {
        const labels = ['Cash PHP'];
        const data = [m.cash_php];
        const colors = ['#7c4dff'];
        const dynamicColors = ['#00f2fe', '#00e676', '#ffea00', '#ff1744', '#f50057'];
        
        let i = 0;
        for (const a of m.assets) {
            labels.push(a.symbol);
            data.push(a.value_php);
            colors.push(dynamicColors[i % dynamicColors.length]);
            i++;
        }
        
        allocationChart.data.labels = labels;
        allocationChart.data.datasets[0].data = data;
        allocationChart.data.datasets[0].backgroundColor = colors;
        allocationChart.update();
    }"""

content = content.replace(old_charts, new_charts)

with open("web/static/script.js", "w") as f:
    f.write(content)
print("Done patching script.js")
