#!/bin/bash
# ============================================
# Furina Bot — Quick Update Script
# ============================================
# Run this to pull latest code and restart the bot.
# Usage: chmod +x deploy/update.sh && sudo deploy/update.sh
# ============================================

BOT_DIR="/home/furina/furina-bot"

echo "✧ Updating Furina Bot..."

cd "$BOT_DIR"

# Pull latest
echo "[1/3] Pulling latest code..."
sudo -u furina git pull

# Update dependencies (in case requirements changed)
echo "[2/3] Updating dependencies..."
sudo -u furina venv/bin/pip install -r requirements.txt --quiet

# Restart
echo "[3/3] Restarting bot..."
sudo systemctl restart furina-bot

# Wait and show status
sleep 2
echo ""
echo "✧ Bot status:"
systemctl status furina-bot --no-pager -l | head -15
echo ""
echo "✧ Recent logs:"
journalctl -u furina-bot -n 10 --no-pager
