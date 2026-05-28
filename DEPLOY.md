# 🚀 Deployment Guide: Running the VolumeRSI Multi-Asset Bot 24/7

This guide walks you through deploying the live trading bot and glassmorphic web dashboard to a cloud server so it runs continuously without your computer being on.

---

## Step 1: Choose a Free Cloud Provider

Because the bot uses the Binance API (which bans US IP addresses), you must host your server in **Asia** or **Europe**. 

| Provider | Region | Price | Recommended? |
|---|---|---|---|
| **Oracle Cloud Free Tier** | Singapore / Tokyo | **100% Free** | ⭐ **Best Option** (Always-Free ARM instances) |
| **Google Cloud Platform (GCP)** | Singapore (`asia-southeast1`) | ~$5/mo | Requires using GCP Trial Credits or paying |

### Create the Server (Google Cloud Example)
1. Go to Google Cloud Console > **Compute Engine** > **VM Instances**.
2. Create a new instance in **`asia-southeast1` (Singapore)**.
3. Select the **`e2-micro`** machine.
4. Under Boot Disk, select **Ubuntu 26.04 LTS**.
5. Note the server's **External IP address**.

---

## Step 2: Connect to Your Server

You can connect using Google Cloud's **SSH-in-Browser** button, or SSH directly from your terminal if you added an SSH key:

```bash
ssh username@YOUR_EXTERNAL_IP
```

---

## Step 3: Install Docker and Clone the Repository

Run these commands sequentially on your Cloud Server:

```bash
# Update system
sudo apt update && sudo apt install docker.io docker-compose -y

# Clone your repository
git clone https://github.com/YOUR_USERNAME/autotrade.git
cd autotrade
```

---

## Step 4: Configure the Environment

We excluded the `.env` file from GitHub for security. You must create it manually on the server:

```bash
# Copy the template
cp .env.example .env

# Edit the file to add your Discord Webhook URL
nano .env
```

Paste your Discord Webhook URL inside (and press `Ctrl+O`, `Enter`, `Ctrl+X` to save):
```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

---

## Step 5: Initialize the Database and Launch 🚀

**CRITICAL DOCKER FIX:** You must create an empty database file *before* running Docker Compose, otherwise Docker will accidentally create a folder instead of a file and the bot will crash!

```bash
# 1. Create the empty file
touch live_trading.db

# 2. Build and launch the bot and dashboard permanently
sudo docker-compose up -d --build
```

That's it! The bot is now running 24/7. 

### Verify It's Running

```bash
# View real-time streaming bot ticks
sudo docker compose logs -f trader
```

---

## Step 6: Access the Glassmorphic Dashboard

By default, Google Cloud blocks incoming internet traffic. You need to open **Port 8000**:
1. Go to **VPC Network** > **Firewall** in Google Cloud.
2. Click **Create Firewall Rule**.
3. Targets: `All instances in the network`
4. Source IPv4: `0.0.0.0/0`
5. Protocol/Port: `TCP` port `8000`.

Open your browser and navigate to:
```
http://YOUR_EXTERNAL_IP:8000
```

---

## 🔧 Useful Commands / Troubleshooting

**Graceful Shutdown:**
```bash
# Safely stops the bot and triggers a Discord shutdown alert
sudo docker compose down
```

**Bot crashed with "unable to open database file"?**
You forgot the `touch live_trading.db` step! Run this to fix it:
```bash
sudo docker compose down
sudo rm -rf live_trading.db
touch live_trading.db
sudo docker compose up -d --build
```

**Applying an Update from GitHub:**
```bash
sudo docker compose down
git pull
sudo docker compose up -d --build
```
