// Global Chart Instances
let equityChart = null;
let allocationChart = null;

// Reconnect settings
let wsRetryDelay = 1000;
let ws = null;

// Document Ready
document.addEventListener("DOMContentLoaded", () => {
    initializeCharts();
    connectWebSocket();
    loadTrades();
});

// Initialize Chart.js Instances
function initializeCharts() {
    // 1. Equity Curve Chart
    const equityCtx = document.getElementById('equityChart').getContext('2d');
    equityChart = new Chart(equityCtx, {
        type: 'line',
        data: {
            labels: ['Initial'],
            datasets: [{
                label: 'Portfolio Balance (PHP)',
                data: [500000.0],
                borderColor: '#7c4dff',
                backgroundColor: 'rgba(124, 77, 255, 0.05)',
                borderWidth: 3,
                fill: true,
                tension: 0.35,
                pointRadius: 4,
                pointBackgroundColor: '#00f2fe',
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#9ca3af', font: { family: 'Outfit' } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: {
                        color: '#9ca3af',
                        font: { family: 'Outfit' },
                        callback: function(value) {
                            return '₱' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });

    // 2. Asset Allocation Chart
    const allocationCtx = document.getElementById('allocationChart').getContext('2d');
    allocationChart = new Chart(allocationCtx, {
        type: 'doughnut',
        data: {
            labels: ['Cash PHP', 'Crypto Position'],
            datasets: [{
                data: [100.0, 0.0],
                backgroundColor: ['#7c4dff', '#00f2fe'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#f3f4f6',
                        font: { family: 'Outfit', size: 12 },
                        padding: 15
                    }
                }
            },
            cutout: '70%'
        }
    });
}

// Connect to the backend WebSocket
function connectWebSocket() {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;

    console.log(`[WebSocket] Connecting to ${wsUrl}...`);
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("[WebSocket] Connection established.");
        wsRetryDelay = 1000; // Reset retry interval
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateDashboardDOM(data.metrics);
            updateCharts(data.metrics, data.equity_curve);
        } catch (err) {
            console.error("[WebSocket message error]", err);
        }
    };

    ws.onclose = () => {
        console.log(`[WebSocket] Disconnected. Reconnecting in ${wsRetryDelay}ms...`);
        setTimeout(connectWebSocket, wsRetryDelay);
        wsRetryDelay = Math.min(wsRetryDelay * 2, 30000); // Exponential backoff
    };

    ws.onerror = (error) => {
        console.error("[WebSocket error]", error);
        ws.close();
    };
}

// Update DOM elements with live WebSocket metrics
function updateDashboardDOM(m) {
    if (!m) return;

    // Price ticker (now Portfolio Value)
    document.getElementById("header-total-usd").innerText = `$${m.total_value_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} USD`;
    document.getElementById("header-active-assets").innerText = `${m.assets ? m.assets.length : 0} Active Asset${(m.assets && m.assets.length !== 1) ? 's' : ''}`;

    // Portfolio metrics
    document.getElementById("total-val-php").innerText = `₱${m.total_value_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;
    document.getElementById("total-val-usd").innerText = `$${m.total_value_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} USD`;
    document.getElementById("cash-val-php").innerText = `₱${m.cash_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;
    document.getElementById("assets-count-val").innerText = `${m.assets ? m.assets.length : 0} Asset${(m.assets && m.assets.length !== 1) ? 's' : ''}`;
    document.getElementById("assets-val-php").innerText = `Value: ₱${(m.total_assets_php || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;

    // PnL display styling
    const profitEl = document.getElementById("profit-val-php");
    const profitPctEl = document.getElementById("profit-val-pct");
    const profitCard = document.getElementById("profit-card");

    const profitSign = m.total_profit_php >= 0 ? "+" : "";
    profitEl.innerText = `₱${profitSign}${m.total_profit_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} PHP`;
    profitPctEl.innerText = `${profitSign}${m.total_profit_pct.toFixed(2)}%`;

    if (m.total_profit_php >= 0) {
        profitEl.className = "card-value text-profit";
        profitPctEl.className = "card-sub text-profit";
        profitCard.style.borderColor = "rgba(0, 230, 118, 0.25)";
    } else {
        profitEl.className = "card-value text-loss";
        profitPctEl.className = "card-sub text-loss";
        profitCard.style.borderColor = "rgba(255, 23, 68, 0.25)";
    }

    // Win Rate and Trade Counts
    document.getElementById("win-rate-val").innerText = `${m.win_rate.toFixed(2)}%`;
    document.getElementById("trades-count-val").innerText = m.total_trades;

    // Active Position alert banner logic
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
        // Surgical DOM updates instead of innerHTML thrashing
        const existingEmpty = assetsGrid.querySelector('.empty-state');
        if (existingEmpty) assetsGrid.removeChild(existingEmpty);
        
        m.assets.forEach(a => {
            const safeSymbol = a.symbol.replace('/', '-');
            let card = document.getElementById(`asset-card-${safeSymbol}`);
            if (!card) {
                card = document.createElement('div');
                card.id = `asset-card-${safeSymbol}`;
                card.className = "asset-card";
                card.innerHTML = `
                    <div class="asset-header">
                        <div class="asset-symbol">${a.symbol}</div>
                        <div class="asset-icon"><i class="${a.symbol.includes('BTC') ? 'fa-brands fa-bitcoin' : (a.symbol.includes('ETH') ? 'fa-brands fa-ethereum' : 'fa-solid fa-coins')}"></i></div>
                    </div>
                    <div class="asset-amount" id="asset-amt-${safeSymbol}"></div>
                    <div class="asset-value" id="asset-val-${safeSymbol}"></div>
                    <div class="asset-price">
                        <span>Price</span>
                        <span class="price-val" id="asset-price-${safeSymbol}"></span>
                    </div>
                `;
                assetsGrid.appendChild(card);
            }
            document.getElementById(`asset-amt-${safeSymbol}`).innerText = a.amount.toFixed(6);
            document.getElementById(`asset-val-${safeSymbol}`).innerText = \`₱\${a.value_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}\`;
            document.getElementById(`asset-price-${safeSymbol}`).innerText = \`$\${a.price_usd.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}\`;
        });
        
        // Remove stale cards
        Array.from(assetsGrid.children).forEach(child => {
            if (child.id && child.id.startsWith('asset-card-')) {
                const sym = child.id.replace('asset-card-', '').replace('-', '/');
                if (!m.assets.find(a => a.symbol === sym)) {
                    assetsGrid.removeChild(child);
                }
            }
        });
    } else {
        assetsGrid.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-ghost empty-icon"></i>
                <p>No active assets...</p>
            </div>
        `;
    }

    // Proactively reload trade list if the status changes
    // (This works as an automatic event listener when transactions open/close)
    const prevTradesCount = parseInt(document.getElementById("trades-count-val").dataset.lastCount || "0");
    if (m.total_trades !== prevTradesCount) {
        document.getElementById("trades-count-val").dataset.lastCount = m.total_trades;
        loadTrades();
    }
}

// Update Chart.js datasets
function updateCharts(m, equityData) {
    if (!m) return;

    // 1. Update Asset Allocation Doughnut Chart
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
    }

    // 2. Update Equity Curve Line Chart
    if (equityData && equityData.length > 0) {
        const labels = equityData.map(pt => pt.timestamp);
        const balances = equityData.map(pt => pt.balance);
        equityChart.data.labels = labels;
        equityChart.data.datasets[0].data = balances;
        equityChart.update();
    }
}

// Fetch and render trades from HTTP API endpoint
async function loadTrades() {
    const tbody = document.getElementById("trades-tbody");
    try {
        const response = await fetch("/api/trades");
        if (!response.ok) throw new Error("Failed to load trade logs");
        const trades = await response.json();

        if (trades.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" class="text-center">No trades recorded yet. Bot is searching for entry signals...</td></tr>`;
            return;
        }

        tbody.innerHTML = trades.map(t => {
            const entryDate = t.entry_time;
            const exitDate = t.exit_time || "—";
            const entryPrice = `₱${t.entry_price_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            const exitPrice = t.exit_price_php ? `₱${t.exit_price_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : "—";
            const btcSize = `${t.size.toFixed(6)} ${t.symbol ? t.symbol.split('/')[0] : ''}`;
            const totalFee = `₱${t.fee_php.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
            
            let profitStr = "—";
            let profitClass = "";
            if (t.status === 'CLOSED') {
                const profitVal = parseFloat(t.profit_php || 0.0);
                const profitSign = profitVal >= 0 ? "+" : "";
                const entryVal = t.size * t.entry_price_php;
                const profitPct = entryVal > 0 ? (profitVal / entryVal) * 100.0 : 0.0;
                
                profitStr = `₱${profitSign}${profitVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} (${profitSign}${profitPct.toFixed(2)}%)`;
                profitClass = profitVal >= 0 ? "text-profit" : "text-loss";
            }

            const typeBadge = t.exit_price_usd ? `<span class="badge sell">SELL</span>` : `<span class="badge buy">BUY</span>`;
            const statusBadge = t.status === 'OPEN' ? `<span class="badge status-open">OPEN</span>` : `<span class="badge status-closed">CLOSED</span>`;

            return `
                <tr>
                    <td>#${t.id}</td>
                    <td>${typeBadge}</td>
                    <td>${entryDate}</td>
                    <td>${exitDate}</td>
                    <td>${entryPrice}</td>
                    <td>${exitPrice}</td>
                    <td>${btcSize}</td>
                    <td class="${profitClass}">${profitStr}</td>
                    <td>${totalFee}</td>
                    <td>${statusBadge}</td>
                </tr>
            `;
        }).join("");

    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="10" class="text-center text-loss"><i class="fa-solid fa-triangle-exclamation"></i> Error loading trade logs: ${err.message}</td></tr>`;
    }
}
