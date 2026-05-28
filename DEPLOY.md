# 🚀 Deployment Guide: Running the BTC Algo Trader 24/7

This guide walks you through deploying the trading bot and web dashboard to a cheap VPS so it runs continuously without your computer being on.

---

## Step 1: Choose a VPS Provider

You need a small Linux server. Here are the cheapest options:

| Provider | Cheapest Plan | RAM | Price/Month | Link |
|---|---|---|---|---|
| **Hetzner** (Recommended) | CX22 | 2 GB | **€3.79 (~₱240)** | [hetzner.com/cloud](https://www.hetzner.com/cloud) |
| **DigitalOcean** | Basic Droplet | 1 GB | $6 (~₱370) | [digitalocean.com](https://www.digitalocean.com) |
| **Vultr** | Cloud Compute | 1 GB | $5 (~₱310) | [vultr.com](https://www.vultr.com) |
| **Linode (Akamai)** | Nanode | 1 GB | $5 (~₱310) | [linode.com](https://www.linode.com) |

> [!TIP]
> **Hetzner CX22** is the best value — 2 GB RAM, 20 GB SSD, located in Singapore (low latency to Binance). The bot uses ~100 MB RAM so even 1 GB is plenty.

### Create the Server
1. Sign up and create an **Ubuntu 24.04** server
2. Choose the **Singapore** or **closest region** to minimize Binance API latency
3. Add your **SSH key** during setup (or use a password)
4. Note the server's **IP address** (e.g. `167.235.xx.xx`)

---

## Step 2: Connect to Your Server

```bash
ssh root@YOUR_SERVER_IP
```

---

## Step 3: Install Docker

Run these commands on your VPS:

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Verify Docker is installed
docker --version
docker compose version
```

---

## Step 4: Upload the Project

**Option A: Git (Recommended)**
If your project is in a Git repository:
```bash
# On your VPS
git clone https://github.com/YOUR_USERNAME/btc-algo-trader.git
cd btc-algo-trader
```

**Option B: SCP (Direct Upload)**
From your local machine:
```bash
# From your local machine (not the VPS)
scp -r /home/arvin/Project/btc-algo-trader root@YOUR_SERVER_IP:/root/btc-algo-trader
```
Then on the VPS:
```bash
cd /root/btc-algo-trader
```

---

## Step 5: Configure Environment

Create the `.env` file on the server:

```bash
nano .env
```

Paste your configuration:
```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_HERE
PHP_USD_RATE=61.55
```

Save with `Ctrl+X`, then `Y`, then `Enter`.

---

## Step 6: Launch the Bot 🚀

```bash
# Build and start both the trading bot and web dashboard
docker compose up -d --build
```

That's it! The bot is now running 24/7. Docker will automatically restart it if it crashes.

### Verify It's Running

```bash
# Check container status
docker compose ps

# View live trading bot logs
docker compose logs -f trader

# View dashboard logs
docker compose logs -f dashboard
```

You should see output like:
```
btc-trader | [2026-05-27 15:08:46 PHT] Connected! Listening for real-time ticks...
btc-dashboard | INFO: Uvicorn running on http://0.0.0.0:8000
```

### Access the Web Dashboard
Open your browser and go to:
```
http://YOUR_SERVER_IP:8000
```

---

## Step 7: Useful Commands

```bash
# Stop everything
docker compose down

# Restart the bot (after changing strategy params)
docker compose restart trader

# Rebuild after code changes
docker compose up -d --build

# View real-time bot logs
docker compose logs -f trader

# Check resource usage
docker stats
```

---

## Step 8: Change Strategy Parameters

Edit the `docker-compose.yml` file to adjust strategy parameters:

```bash
nano docker-compose.yml
```

Modify the `command` section under the `trader` service, then restart:

```bash
docker compose restart trader
```

---

## 🔒 Security: Protect the Dashboard

By default, the dashboard is open to anyone who knows the server IP. To add basic protection:

### Option A: Firewall (Simplest)
Only allow your home IP to access the dashboard:
```bash
# Allow SSH from anywhere
ufw allow 22

# Allow dashboard only from your IP
ufw allow from YOUR_HOME_IP to any port 8000

# Enable firewall
ufw enable
```

### Option B: SSH Tunnel (Most Secure)
Don't expose port 8000 at all. Access it through an SSH tunnel:
```bash
# On your local machine
ssh -L 8000:localhost:8000 root@YOUR_SERVER_IP

# Then open http://localhost:8000 in your browser
```

---

## 💰 Cost Summary

| Item | Monthly Cost |
|---|---|
| Hetzner CX22 VPS | ~₱240 |
| Domain name (optional) | ~₱50 |
| **Total** | **~₱240–290/month** |

The bot costs less than a cup of coffee per day to run 24/7.

---

## 🔧 Troubleshooting

**Bot container keeps restarting?**
```bash
docker compose logs trader
```
Check for Python errors or network issues.

**SQLite database locked?**
This can happen if both containers write simultaneously. The current setup has only the trader writing and the dashboard reading, which is safe.

**Want to reset the portfolio?**
```bash
docker compose down
rm live_trading.db
docker compose up -d
```
This will start fresh with ₱500,000 PHP paper money.
