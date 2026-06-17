# 📱 Deploy Furina Bot di Termux (HP Android Lama)

Kalau Google Cloud gak berhasil, ini plan B yang **100% gratis**.
Yang dibutuhin: HP Android bekas + charger + WiFi.

---

## Step 1: Install Termux

> ⚠️ Install dari **F-Droid**, BUKAN Play Store (versi Play Store udah outdated)

1. Buka browser HP → [f-droid.org](https://f-droid.org)
2. Download F-Droid APK → install
3. Buka F-Droid → cari **Termux** → install
4. Buka Termux

---

## Step 2: Setup Environment

```bash
# Update packages
pkg update && pkg upgrade -y

# Install Python, Git, dll
pkg install python git openssh -y

# Cek Python
python --version   # harus 3.x
```

---

## Step 3: Clone & Setup Bot

```bash
# Clone repo
git clone https://github.com/<USERNAME>/<REPO>.git ~/furina-bot
cd ~/furina-bot

# Install dependencies
pip install -r requirements.txt

# Bikin .env
cp .env.example .env
nano .env
# Isi DISCORD_TOKEN dan GROQ_API_KEY
# Save: Ctrl+O, Enter, Ctrl+X
```

**Tanpa GitHub:**
```bash
# Dari PC, kirim file via USB/cloud/Telegram
# Taruh di ~/furina-bot/
```

---

## Step 4: Jalanin Bot

```bash
cd ~/furina-bot
python bot.py
```

---

## Step 5: Biar Gak Mati Saat HP Lock

### A. Termux Wake Lock (WAJIB)
```bash
# Dari notification bar Termux → tap "Acquire Wakelock"
# Atau via command:
termux-wake-lock
```

### B. Setting HP
1. **Matikan Battery Optimization** untuk Termux:
   - Settings → Apps → Termux → Battery → Unrestricted
2. **Matikan Auto-Sleep** (atau set ke 30 menit):
   - Settings → Display → Sleep → 30 minutes
3. **Kunci Termux di Recent Apps** (swipe lock):
   - Buka recent apps → swipe Termux ke bawah → lock

### C. Jalanin di Background dengan tmux
```bash
# Install tmux
pkg install tmux -y

# Bikin session baru
tmux new -s furina

# Jalanin bot
cd ~/furina-bot
python bot.py

# Detach (bot tetap jalan): Ctrl+B lalu tekan D
# Kamu bisa tutup Termux, bot tetap running

# Balik ke session:
tmux attach -t furina

# List sessions:
tmux ls
```

---

## Step 6: Auto-Start Saat Termux Dibuka

```bash
# Bikin startup script
mkdir -p ~/.termux
nano ~/.termux/boot/start-bot.sh
```

Paste:
```bash
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd ~/furina-bot
python bot.py
```

```bash
chmod +x ~/.termux/boot/start-bot.sh

# Install Termux:Boot dari F-Droid buat auto-start saat HP reboot
# F-Droid → cari "Termux:Boot" → install
```

---

## 🔄 Update Bot

```bash
# Attach ke tmux session dulu
tmux attach -t furina

# Stop bot: Ctrl+C
cd ~/furina-bot
git pull
python bot.py

# Detach lagi: Ctrl+B lalu D
```

---

## 🔧 Troubleshooting

### Bot mati saat HP lock
→ Pastiin wake lock aktif: `termux-wake-lock`
→ Matikan battery optimization untuk Termux
→ Pakai tmux supaya gak tergantung foreground

### Error "externally-managed-environment" saat pip install
```bash
pip install -r requirements.txt --break-system-packages
```

### Storage penuh
```bash
# Cek
df -h

# Bersihin cache
pip cache purge
pkg clean
```

### HP panas
→ Normal kalau jalan 24/7, tapi kalau terlalu panas:
→ Lepas case HP, taruh di tempat dingin
→ Kurangin brightness ke minimum
→ Matikan WiFi scanning background

---

## Tips

- **Colok charger** terus (tapi kalau bisa, cabut saat 80% → colok lagi saat 20% biar baterai awet)
- **Matikan semua app lain** — HP ini dedicated buat bot
- **Pakai HP lama** yang udah gak kepake — perfect use case
- **WiFi harus stabil** — kalau sering putus, bot reconnect terus
- **tmux wajib** — kalau gak pake tmux, bot mati saat Termux ke background
