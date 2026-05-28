with open("web/templates/index.html", "r") as f:
    content = f.read()

old_header = """                <div class="header-ticker">
                    <div class="ticker-label">BTC Price</div>
                    <div class="ticker-value" id="btc-price-val">₱0.00 PHP</div>
                    <div class="ticker-usd" id="btc-price-usd">$0.00 USD</div>
                </div>"""

new_header = """                <div class="header-ticker">
                    <div class="ticker-label">Portfolio Value (USD)</div>
                    <div class="ticker-value" id="header-total-usd">$0.00 USD</div>
                    <div class="ticker-usd" id="header-active-assets">0 Active Assets</div>
                </div>"""

content = content.replace(old_header, new_header)

old_banner = """            <!-- Active Position Alert Box -->
            <div id="position-banner" class="position-banner hidden">
                <div class="banner-icon"><i class="fa-solid fa-circle-info"></i></div>
                <div class="banner-content">
                    <strong>Active Position Open:</strong> Holding <span id="banner-btc-size">0.000000</span> BTC. Entered at <span id="banner-entry-price">₱0.00</span> PHP.
                </div>
            </div>"""

new_banner = """            <!-- Active Position Alert Box -->
            <div id="position-banner" class="position-banner hidden">
                <div class="banner-icon"><i class="fa-solid fa-circle-info"></i></div>
                <div class="banner-content">
                    <strong>Active Position Open:</strong> Holding <span id="banner-assets-count">0</span> asset(s).
                </div>
            </div>"""

content = content.replace(old_banner, new_banner)

old_card = """                <div class="stat-card">
                    <div class="card-header">
                        <span>BTC Holdings</span>
                        <i class="fa-brands fa-bitcoin card-icon btc-icon"></i>
                    </div>
                    <div class="card-value" id="holdings-val-btc">0.000000 BTC</div>
                    <div class="card-sub" id="holdings-val-php">Value: ₱0.00 PHP</div>
                </div>"""

new_card = """                <div class="stat-card">
                    <div class="card-header">
                        <span>Asset Allocation</span>
                        <i class="fa-solid fa-layer-group card-icon"></i>
                    </div>
                    <div class="card-value" id="assets-count-val">0 Assets</div>
                    <div class="card-sub" id="assets-val-php">Value: ₱0.00 PHP</div>
                </div>"""

content = content.replace(old_card, new_card)

# Insert Assets section before Charts Section
charts_section = """            <!-- Charts Section -->"""
assets_section = """            <!-- Current Assets Section -->
            <section class="assets-section">
                <div class="section-header">
                    <h2>Current Assets</h2>
                </div>
                <div class="assets-grid" id="assets-grid">
                    <div class="text-secondary" style="grid-column: 1 / -1; text-align: center; padding: 2rem;">No active assets...</div>
                </div>
            </section>

            <!-- Charts Section -->"""

content = content.replace(charts_section, assets_section)

with open("web/templates/index.html", "w") as f:
    f.write(content)
print("Done patching index.html")
