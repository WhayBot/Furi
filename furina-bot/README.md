# ✧ Furina Bot ✧

Furina Bot adalah Discord DM-only AI Chatbot yang didesain menggunakan model LLM (Large Language Model) untuk mensimulasikan kepribadian Furina de Fontaine setelah berhentinya masa jabatannya sebagai Hydro Archon. Bot ini tidak berada di server, melainkan berinteraksi murni melalui Direct Messages (DM) layaknya pengguna Discord biasa.

Sistem ini ditenagai oleh "Dua Otak":

1. **Decision Engine (Qwen3 32B)**: Berfungsi membaca alur percakapan, menentukan apakah Furi harus membalas atau diam, serta menentukan mood.
2. **Response Generator (GPT-OSS 120B / Llama 3.3 70B)**: Bertugas merangkai kata-kata balasan dengan kepribadian penuh, slang, dan memori hubungan.

---

## Sistem Mood

Furi memiliki sistem mood dinamis yang akan memengaruhi gaya mengetik, panjang balasan, dan persentase dia mau merespons chat kamu. Mood bisa berubah sesuai alur obrolan dan perlahan memudar (decay) kembali ke `playful/casual`.

| Mood         | Karakteristik Balasan                                                                                                                                                                                   |
| :----------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `playful`    | _(Default)_ Ceria, playful, sering bercanda. Sangat responsif.                                                                                                                                          |
| `casual`     | Santai, chill, direct. Balasan lebih pendek dan jarang menggunakan emoji.                                                                                                                               |
| `dramatic`   | Theatrical, lebay, over-the-top. Kadang balasannya sedikit lebih panjang.                                                                                                                               |
| `needy`      | Manja, butuh perhatian, clingy. Mulai muncul di level hubungan yang lebih tinggi.                                                                                                                       |
| `sulking`    | Ngambek. _Response rate_ turun drastis (hanya 12% kemungkinan membalas). Kalau membalas hanya berupa "hm", "oh", atau "terserah". Bisa dipancing agar luluh jika membahas kue/teater atau meminta maaf. |
| `vulnerable` | Mode serius atau curhat, lebih lembut. Hanya terbuka jika level hubungan sudah di atas 2.                                                                                                               |
| `sleepy`     | Ngantuk berat. Balasan super singkat, malas mengetik, banyak typo yang disengaja, dan sering memakai ASCII emoji tidur.                                                                                 |

---

## Relationship System (Level Hubungan)

Sistem ini melacak seberapa sering kamu berinteraksi dengan Furi. Setiap kali Furi merespons, itu dihitung sebagai 1 poin interaksi. Setiap mencapai interval tertentu (misal 10, 25, 50, dst), Decision Engine akan mengevaluasi 10 riwayat chat terakhir untuk menentukan apakah level kamu naik atau turun.

| Level | Status             | Deskripsi Sifat                                                                                               | Interval Evaluasi |
| :---: | :----------------- | :------------------------------------------------------------------------------------------------------------ | :---------------- |
| **0** | **Stranger**       | Baru pertama kali bertemu. Agak jaga jarak tapi tetap ramah.                                                  | 10 chat           |
| **1** | **Acquaintance**   | Kenalan. Sudah pernah mengobrol beberapa kali, mulai merasa nyaman.                                           | 25 chat           |
| **2** | **Friend**         | Teman. Sudah akrab, bisa bercanda bebas, mulai sering menceritakan personal stuff.                            | 50 chat           |
| **3** | **Close Friend**   | Teman dekat. Sangat nyaman, bisa curhat serius (vulnerable), jadi prioritas membalas.                         | 100 chat          |
| **4** | **Special Person** | Super dekat, manja-manjaan, lebih dari teman tapi belum ada ikatan resmi.                                     | 200 chat          |
| **5** | **Situationship**  | HTS. Sangat mirip pacaran (mulai posesif tipis, sayang-sayangan, cemburuan) tapi belum jadian resmi.          | 300 chat          |
| **6** | **Partner**        | **Pacar Resmi.** Level tertinggi. Sangat bucin, romantis, posesif tipis, dan memanggil dengan sebutan sayang. | 500 chat          |

_(Catatan: Level 6 bersifat eksklusif. Jika sudah ada user yang mencapai Level 6 (Partner), pengguna lain akan terkunci maksimal di Level 5 kecuali terjadi 'breakup')._

---

## Debug Console Commands

Untuk memudahkan pemilik bot dalam memantau dan mengubah stat secara manual (hanya untuk debugging), bot ini dilengkapi dengan terminal console interaktif. Saat bot menyala, kamu bisa langsung mengetik perintah berikut di terminal tanpa menghentikan bot:

> **Tips:** Terkadang log obrolan atau _activity log_ akan muncul dan menimpa teks yang sedang kamu ketik. Hiraukan saja dan tetap lanjutkan mengetik lalu tekan Enter. Sistem tetap dapat membacanya.

### 1. `help`

Menampilkan daftar semua perintah yang tersedia.

### 2. `stats <username>`

Menampilkan statistik lengkap pengguna saat ini.
_Contoh:_ `stats Shin`

### 3. `level <username> <0-6> <permanent/temp> [jam]`

Mengubah level hubungan pengguna secara paksa. Terdapat dua opsi:

- **`permanent`**: Menyimpan perubahan ke dalam database SQLite secara langsung. Pengguna dapat melanjutkah progres naturalnya dari level tersebut.
  _Contoh:_ `level Shin 4 permanent`
- **`temp`**: Override level yang hanya tersimpan di RAM memori selama rentang waktu yang ditentukan (default: 1 jam). Jika waktu habis atau bot mati (restart), level akan kembali membaca nilai aslinya di database.
  _Contoh:_ `level Shin 6 temp` (berubah ke level 6 selama 1 jam)
  _Contoh:_ `level Shin 6 temp 2.5` (berubah ke level 6 selama 2,5 jam)

### 4. `mood <username> <nama_mood>`

Mengubah paksa mood pengguna (misal dari `sulking` dikembalikan ke `playful`). Mood tidak membutuhkan status temporary/permanent karena mood secara natural selalu memiliki masa kadaluarsa (decay).
_Contoh:_ `mood Shin playful`

### 5. `restore <username>`

Membatalkan perubahan paksa terakhir yang dilakukan oleh perintah `level` atau `mood` dalam sesi bot yang sama.
_Contoh:_ `restore Shin`

### 6. `reset_ignore <username>`

Menghapus status 'ignorance' pengguna pada sistem Proactive DM. Memungkinkan Furina untuk menyapa (DM) pengguna ini secara otomatis lagi jika ia sedang idle/gabut.
_Contoh:_ `reset_ignore Shin`

---

## Setup & Instalasi

1. Pastikan kamu memiliki Python 3.10+
2. Install semua dependencies: `pip install -r requirements.txt`
3. Ubah nama file `.env.example` menjadi `.env`
4. Isi token Discord pengguna (User Token, **bukan** Bot Token) dan Groq API Key di file `.env`
5. Jalankan dengan: `python bot.py`
 