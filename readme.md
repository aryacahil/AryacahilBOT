
---

# 🤖 AryacahilBOT

Bot Discord multifungsi dengan sistem ekonomi (WoWoCash), slash command, dan fitur modular menggunakan Cogs.

## 🚀 Fitur Utama

* 💰 Sistem Ekonomi (WoWoCash)
* 🎁 Daily reward
* 💸 Transfer saldo antar user
* 🏦 Cek saldo
* 🛠️ Slash Commands (`/`)
* 📦 Modular system menggunakan Cogs
* 🔒 Permission-based command

---

## 🛠️ Teknologi yang Digunakan

* Python 3.10+
* discord.py 2.x
* SQLite / JSON (sesuaikan dengan database kamu)
* Virtual Environment (.venv)

---

## 📂 Struktur Folder

```
AryacahilBOT/
│
├── bot.py
├── cogs/
│   ├── wowocash.py
│   └── ...
├── data/
│   └── database.db
├── .env
├── requirements.txt
└── README.md
```

---

## ⚙️ Cara Install

### 1️⃣ Clone Repository

```bash
git clone https://github.com/USERNAME/AryacahilBOT.git
cd AryacahilBOT
```

### 2️⃣ Buat Virtual Environment

```bash
python -m venv .venv
```

Aktifkan:

**Windows:**

```bash
.venv\Scripts\activate
```

**Mac/Linux:**

```bash
source .venv/bin/activate
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔑 Setup Token Bot

1. Buat bot di [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Copy **Bot Token**
3. Simpan di file `.env`

Contoh `.env`:

```
DISCORD_TOKEN=YOUR_BOT_TOKEN_HERE
```

---

## ▶️ Menjalankan Bot

```bash
python bot.py
```

Jika berhasil, bot akan online di server Discord kamu.

---

## 💰 Contoh Command WoWoCash

| Command     | Deskripsi                |
| ----------- | ------------------------ |
| `/balance`  | Cek saldo                |
| `/daily`    | Ambil daily reward       |
| `/transfer` | Kirim saldo ke user lain |

(Sesuaikan dengan command asli di wowocash.py kamu)

---

## 🔧 Development

Untuk menambahkan fitur baru:

1. Buat file baru di folder `cogs/`
2. Gunakan struktur Cog:

```python
from discord.ext import commands

class NamaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(NamaCog(bot))
```

---

## 📌 Notes

* Pastikan bot memiliki permission yang cukup di server.
* Gunakan discord.py versi terbaru (2.x) untuk slash command.
* Jangan upload token ke GitHub.

---

## 📄 License

Project ini bebas digunakan untuk pembelajaran.

---