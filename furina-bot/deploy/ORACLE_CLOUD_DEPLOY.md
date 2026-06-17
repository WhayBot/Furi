# ☁️ Deploy Furina Bot ke Oracle Cloud (Free Tier)

## Kenapa Oracle Cloud?
- **Gratis selamanya** — bukan trial, beneran Always Free
- **ARM VM**: 4 core, 24GB RAM (overkill buat bot, tapi gratis wkwk)
- **200GB storage** 
- **Full SSH access** — bisa install apa aja
- **Uptime 99.9%**

---

## Step 1: Bikin Akun Oracle Cloud

1. Buka [cloud.oracle.com](https://cloud.oracle.com) → **Sign Up**
2. Isi data (butuh credit card buat verifikasi, tapi **TIDAK akan dicharge**)
3. Pilih **Home Region** → **ap-singapore-1** (Singapore) atau yang paling deket
4. Tunggu approval (biasanya instan, kadang 1-2 hari)

> ⚠️ **PENTING**: Pilih region Singapore/Japan buat latency rendah ke Discord API.

---

## Step 2: Buat VM (Always Free)

1. Login ke Oracle Cloud Console
2. Klik **Create a VM Instance**
3. Setting:
   - **Name**: `furina-bot`
   - **Image**: Ubuntu 22.04 (atau 24.04)
   - **Shape**: Klik **Change Shape** → **Ampere** → **VM.Standard.A1.Flex**
     - OCPU: **1** (bisa sampe 4 gratis)
     - Memory: **6 GB** (bisa sampe 24 gratis)
   - **Networking**: Default VCN, Public subnet, Assign public IPv4
   - **SSH Key**: **Generate key pair** → **Save Private Key** (download `.key` file!)

4. Klik **Create** → tunggu 2-5 menit sampe status `RUNNING`

5. Catat **Public IP Address** (contoh: `132.xxx.xxx.xxx`)

---

## Step 3: Connect ke VM via SSH

### Windows (PowerShell):
```powershell
# Pindahin private key ke folder aman
mkdir ~\.ssh -Force
Move-Item .\ssh-key-*.key ~\.ssh\oracle-vm.key

# Connect
ssh -i ~\.ssh\oracle-vm.key ubuntu@<PUBLIC_IP>
```

### Kalo pake PuTTY:
1. Convert `.key` ke `.ppk` pake PuTTYgen
2. Masukin IP + username `ubuntu` + private key

---

## Step 4: Setup Firewall Oracle Cloud

Bot ini gak butuh port terbuka (outbound only), tapi kalau mau SSH pastiin port 22 terbuka:

1. Oracle Console → **Networking** → **Virtual Cloud Networks**
2. Klik VCN → **Security Lists** → **Default Security List**
3. Pastiin ada **Ingress Rule**:
   - Source: `0.0.0.0/0`, Protocol: TCP, Dest Port: `22`

---

## Step 5: Setup Bot di Server

### Option A: Clone dari GitHub (Recommended)

```bash
# 1. Push code ke GitHub dulu (dari PC lokal)
# Di PC lokal:
cd "d:\Celestarc Technologies\Project\DC-AI\furina-bot"
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<USERNAME>/<REPO>.git
git push -u origin main

# 2. Di server Oracle:
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# Clone repo
git clone https://github.com/<USERNAME>/<REPO>.git ~/furina-bot
cd ~/furina-bot

# Setup Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Buat .env
cp .env.example .env
nano .env    # Isi DISCORD_TOKEN dan GROQ_API_KEY
```

### Option B: Upload langsung (tanpa GitHub)

```bash
# Dari PC lokal (PowerShell):
scp -i ~\.ssh\oracle-vm.key -r "d:\Celestarc Technologies\Project\DC-AI\furina-bot" ubuntu@<PUBLIC_IP>:~/furina-bot

# Atau zip dulu:
Compress-Archive -Path "d:\Celestarc Technologies\Project\DC-AI\furina-bot\*" -DestinationPath furina-bot.zip
scp -i ~\.ssh\oracle-vm.key furina-bot.zip ubuntu@<PUBLIC_IP>:~/

# Di server:
unzip furina-bot.zip -d ~/furina-bot
```

---

## Step 6: Test Bot Dulu

```bash
cd ~/furina-bot
source venv/bin/activate
python bot.py
```

Kalau jalan dan login berhasil → **Ctrl+C** untuk stop, lanjut ke step 7.

---

## Step 7: Bikin Systemd Service (Auto-Start + Auto-Restart)

```bash
sudo nano /etc/systemd/system/furina-bot.service
```

Paste ini:

```ini
[Unit]
Description=Furina Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/furina-bot
ExecStart=/home/ubuntu/furina-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

# Load .env file
EnvironmentFile=/home/ubuntu/furina-bot/.env

[Install]
WantedBy=multi-user.target
```

Aktifkan:

```bash
sudo systemctl daemon-reload
sudo systemctl enable furina-bot    # Auto-start saat boot
sudo systemctl start furina-bot     # Start sekarang
```

---

## Step 8: Cek Status & Logs

```bash
# Status
sudo systemctl status furina-bot

# Live logs (Ctrl+C buat keluar)
sudo journalctl -u furina-bot -f

# Logs 50 baris terakhir
sudo journalctl -u furina-bot -n 50 --no-pager

# Restart bot
sudo systemctl restart furina-bot

# Stop bot
sudo systemctl stop furina-bot
```

---

## 🔄 Update Bot (Setiap Kali Ada Perubahan)

### Kalau pake GitHub:

```bash
# Di PC lokal — push perubahan
git add .
git commit -m "update: fix proactive dm"
git push

# Di server — pull & restart
cd ~/furina-bot
git pull
sudo systemctl restart furina-bot
```

### One-liner update:
```bash
cd ~/furina-bot && git pull && sudo systemctl restart furina-bot
```

### Kalau tanpa GitHub:
```bash
# Dari PC lokal, upload file yang berubah:
scp -i ~\.ssh\oracle-vm.key bot.py ubuntu@<PUBLIC_IP>:~/furina-bot/
scp -i ~\.ssh\oracle-vm.key -r handlers/ ubuntu@<PUBLIC_IP>:~/furina-bot/

# Restart
ssh -i ~\.ssh\oracle-vm.key ubuntu@<PUBLIC_IP> "sudo systemctl restart furina-bot"
```

---

## 🛡️ Tips Keamanan

1. **Jangan commit `.env`** — udah ada di `.gitignore`
2. **Pakai private repo** di GitHub
3. **Update server** berkala:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
4. **Backup database** sesekali:
   ```bash
   cp ~/furina-bot/data/furina.db ~/furina-backup-$(date +%Y%m%d).db
   ```

---

## 🔧 Troubleshooting

### Bot gak jalan setelah restart server
```bash
# Cek apakah service enabled
sudo systemctl is-enabled furina-bot
# Kalau "disabled":
sudo systemctl enable furina-bot
```

### Error "ModuleNotFoundError"
```bash
cd ~/furina-bot
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart furina-bot
```

### Mau ganti .env
```bash
nano ~/furina-bot/.env
sudo systemctl restart furina-bot
```

### Disk penuh (database terlalu besar)
```bash
# Cek size
du -sh ~/furina-bot/data/

# Kalau perlu, backup & reset
cp ~/furina-bot/data/furina.db ~/backup-furina.db
rm ~/furina-bot/data/furina.db
sudo systemctl restart furina-bot
```

---

## 📊 Monitoring (Optional)

### Bikin simple health check script:
```bash
cat > ~/check-bot.sh << 'EOF'
#!/bin/bash
if systemctl is-active --quiet furina-bot; then
    echo "✓ Bot is running"
else
    echo "✗ Bot is DOWN! Restarting..."
    sudo systemctl restart furina-bot
fi
EOF
chmod +x ~/check-bot.sh

# Jalanin tiap 5 menit via cron
crontab -e
# Tambah baris:
# */5 * * * * /home/ubuntu/check-bot.sh >> /home/ubuntu/bot-health.log 2>&1
```

---

## Summary Perintah Penting

| Aksi | Command |
|---|---|
| Start bot | `sudo systemctl start furina-bot` |
| Stop bot | `sudo systemctl stop furina-bot` |
| Restart bot | `sudo systemctl restart furina-bot` |
| Status | `sudo systemctl status furina-bot` |
| Live logs | `sudo journalctl -u furina-bot -f` |
| Update & restart | `cd ~/furina-bot && git pull && sudo systemctl restart furina-bot` |
