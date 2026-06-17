#!/bin/bash
# ============================================
# Furina Bot — Oracle Cloud Setup Script
# ============================================
# Run this on your Oracle Cloud VM after cloning the repo.
# Usage: chmod +x deploy/setup.sh && sudo deploy/setup.sh
# ============================================

set -e

echo "============================================"
echo "  ✧ Furina Bot — Server Setup ✧"
echo "============================================"

# Update system
echo "[1/6] Updating system..."
apt update && apt upgrade -y

# Install Python 3.11+
echo "[2/6] Installing Python..."
apt install -y python3 python3-pip python3-venv git

# Create bot user (security)
echo "[3/6] Creating bot user..."
if ! id "furina" &>/dev/null; then
    useradd -m -s /bin/bash furina
    echo "✓ User 'furina' created"
else
    echo "✓ User 'furina' already exists"
fi

# Setup bot directory
BOT_DIR="/home/furina/furina-bot"
echo "[4/6] Setting up bot directory..."

if [ -d "$BOT_DIR" ]; then
    echo "✓ Bot directory exists, pulling latest..."
    cd "$BOT_DIR"
    sudo -u furina git pull
else
    echo "  Cloning repo..."
    echo "  !! You need to clone your repo manually first !!"
    echo "  Run: sudo -u furina git clone <YOUR_REPO_URL> $BOT_DIR"
    exit 1
fi

# Create virtual environment
echo "[5/6] Setting up Python environment..."
cd "$BOT_DIR"
sudo -u furina python3 -m venv venv
sudo -u furina venv/bin/pip install --upgrade pip
sudo -u furina venv/bin/pip install -r requirements.txt

# Create data directory for database
sudo -u furina mkdir -p data

echo "[6/6] Setting up systemd service..."

# Create systemd service
cat > /etc/systemd/system/furina-bot.service << 'EOF'
[Unit]
Description=Furina Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=furina
WorkingDirectory=/home/furina/furina-bot
ExecStart=/home/furina/furina-bot/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment
EnvironmentFile=/home/furina/furina-bot/.env

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/furina/furina-bot/data

[Install]
WantedBy=multi-user.target
EOF

# Reload and enable
systemctl daemon-reload
systemctl enable furina-bot
echo "✓ Systemd service installed and enabled"

echo ""
echo "============================================"
echo "  ✧ Setup Complete! ✧"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Create .env file:"
echo "     sudo -u furina cp .env.example .env"
echo "     sudo -u furina nano .env"
echo ""
echo "  2. Start the bot:"
echo "     sudo systemctl start furina-bot"
echo ""
echo "  3. Check status:"
echo "     sudo systemctl status furina-bot"
echo ""
echo "  4. View logs:"
echo "     sudo journalctl -u furina-bot -f"
echo ""
echo "  5. Update bot:"
echo "     cd $BOT_DIR && sudo -u furina git pull"
echo "     sudo systemctl restart furina-bot"
echo ""
