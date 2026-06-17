# ☁️ Deploy Furina Bot ke Google Cloud Free Tier

## Apa yang Gratis?
- **e2-micro VM**: 2 vCPU (shared), 1GB RAM — cukup buat bot
- **30GB disk** standard persistent
- **1GB egress/bulan** ke sebagian besar region
- **Gratis selamanya** (bukan trial — Always Free tier)

> ⚠️ Google kasih $300 free credit untuk 90 hari pertama. Setelah itu, selama kamu pakai e2-micro di region yang tepat, tetap GRATIS.

---

## Step 1: Bikin Akun Google Cloud

1. Buka [console.cloud.google.com](https://console.cloud.google.com)
2. Login pakai akun Google biasa
3. Klik **Try Free** / **Get Started**
4. Isi data + credit card (untuk verifikasi, **TIDAK dicharge**)
5. Kamu dapat $300 free credit + Always Free tier

> 💡 Setelah $300 credit habis (90 hari), Google **TIDAK** otomatis charge.
> Kamu harus manually upgrade ke paid account. Kalau gak upgrade, VM tetap jalan selama masuk Always Free tier.

---

## Step 2: Buat VM Instance

### Via Google Cloud Console (Web UI):

1. Buka [console.cloud.google.com/compute](https://console.clocud.google.com/compute)
2. Klik **CREATE INSTANCE**
3. Setting:

| Field | Value |
|---|---|
| **Name** | `furina-bot` |
| **Region** | `us-west1` (Oregon) atau `us-central1` (Iowa) atau `us-east1` (Carolina) |
| **Zone** | Pilih yang mana aja (contoh: `us-west1-b`) |
| **Machine type** | `e2-micro` (2 vCPU, 1 GB memory) |
| **Boot disk** | Klik **Change** → Ubuntu 22.04 LTS, 30 GB Standard |
| **Firewall** | ❌ Gak perlu centang apa-apa (bot outbound only) |

> ⚠️ **HARUS** pilih region `us-west1`, `us-central1`, atau `us-east1` untuk free tier!
> Region lain (asia, europe) **TIDAK gratis**.

4. Klik **CREATE**
5. Tunggu 1-2 menit sampe status ✅ (centang hijau)

---

## Step 3: Connect ke VM

### Option A: Browser SSH (Paling Gampang)
1. Di halaman VM Instances, klik **SSH** di sebelah nama VM
2. Otomatis buka terminal di browser — langsung bisa ketik command

### Option B: SSH dari PC (PowerShell)
```powershell
# Install gcloud CLI dulu: https://cloud.google.com/sdk/docs/install
gcloud compute ssh furina-bot --zone=us-west1-b
```

### Option C: SSH manual
```powershell
# Generate SSH key
ssh-keygen -t rsa -f ~\.ssh\gcloud-key -C "username"

# Tambah public key ke VM:
# Console → VM → Edit → SSH Keys → Add Item → paste isi gcloud-key.pub

# Connect
ssh -i ~\.ssh\gcloud-key username@<EXTERNAL_IP>
```

---

## Step 4: Setup Bot di Server

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git

# 2. Clone repo (dari GitHub)
git clone https://github.com/<USERNAME>/<REPO>.git ~/furina-bot
cd ~/furina-bot

# 3. Setup Python virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Bikin .env
cp .env.example .env
nano .env
# Isi:
#   DISCORD_TOKEN=<token dari browser DevTools>
#   GROQ_API_KEY=<dari console.groq.com>
# Save: Ctrl+O, Enter, Ctrl+X

# 5. Test dulu
python bot.py
# Kalo berhasil login → Ctrl+C untuk stop
```

---

## Step 5: Bikin Systemd Service

```bash
sudo nano /etc/systemd/system/furina-bot.service
```

Paste:
```ini
[Unit]
Description=Furina Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<USERNAME_KAMU>
WorkingDirectory=/home/<USERNAME_KAMU>/furina-bot
ExecStart=/home/<USERNAME_KAMU>/furina-bot/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

> 💡 Ganti `<USERNAME_KAMU>` dengan username SSH kamu (cek dengan command `whoami`)

Aktifkan:
```bash
sudo systemctl daemon-reload
sudo systemctl enable furina-bot
sudo systemctl start furina-bot
```

---

## Step 6: Verifikasi

```bash
# Cek status
sudo systemctl status furina-bot

# Live logs
sudo journalctl -u furina-bot -f

# Harus keliatan:
#   ✧ Furina Bot Online! ✧
#   Logged in as: furi.mi
```

---

## 🔄 Update Bot

```bash
# SSH ke server, lalu:
cd ~/furina-bot
git pull
sudo systemctl restart furina-bot

# Cek logs
sudo journalctl -u furina-bot -n 20 --no-pager
```

---

## 🛡️ Biar Gak Kena Charge

1. **JANGAN** upgrade ke Paid Account kecuali kamu mau
2. Cek billing: [console.cloud.google.com/billing](https://console.cloud.google.com/billing)
3. Set **Budget Alert**: Billing → Budgets → Create Budget → $0 → alert di $0.01
4. Pastiin VM machine type tetap `e2-micro`
5. Pastiin region `us-west1`, `us-central1`, atau `us-east1`

---

## 🔧 Troubleshooting

### VM gak bisa dibuat (quota error)
→ Coba region lain (us-central1 atau us-east1)

### SSH gak bisa connect
→ Pakai browser SSH dari Console (klik tombol SSH di VM list)

### Bot crash terus restart
```bash
sudo journalctl -u furina-bot -n 50 --no-pager
# Baca error message nya
```

### Memory penuh (1GB ketat)
```bash
# Cek memory
free -h

# Bikin swap file (tambahan 1GB virtual memory)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### $300 credit habis, VM mati
→ Kalau kamu belum upgrade ke paid: Google auto-stop semua resources.
→ Upgrade ke paid (gak dicharge selama pakai free tier resources) → start VM lagi.

---

## 📊 Cheat Sheet

| Aksi | Command |
|---|---|
| SSH ke VM | `gcloud compute ssh furina-bot --zone=us-west1-b` |
| Start bot | `sudo systemctl start furina-bot` |
| Stop bot | `sudo systemctl stop furina-bot` |
| Restart | `sudo systemctl restart furina-bot` |
| Status | `sudo systemctl status furina-bot` |
| Live logs | `sudo journalctl -u furina-bot -f` |
| Update | `cd ~/furina-bot && git pull && sudo systemctl restart furina-bot` |
| Disk usage | `df -h` |
| Memory | `free -h` |
| CPU | `top` |
