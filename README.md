# Telegram OSINT Toolkit

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Telegram](https://img.shields.io/badge/Telegram-OSINT-orange)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)

**High-end, local, production-ready Telegram intelligence gathering tool** built for **OSINT**, cybersecurity research, threat intelligence, law enforcement, and authorized military/investigative use.

Powered by **Telethon** + **Rich** with advanced features including proxy/Tor support, live monitoring, bulk search, full exports (JSON/CSV/HTML), member enumeration, and persistent SQLite storage.

> ⚠️ **Legal & Ethical Notice**  
> Use only on public channels/groups or those you are authorized to access. Respect Telegram Terms of Service, rate limits, and all applicable laws. This tool is intended for **defensive, research, and authorized intelligence** purposes only.

---

## ✨ Features

- 🔍 **Advanced Keyword Search** (single chat + bulk across many channels)
- 📡 **Bulk Monitoring** from TXT/JSON channel lists
- 📤 **Full Chat Export** → JSON / CSV / **HTML** reports
- 📎 **Media Download** + **Link Extraction**
- 👥 **Member Enumeration** with JSON export
- 👤 **User / Channel Profiling**
- 🔴 **Live Real-time Monitoring** with keyword alerts
- 🌐 **Proxy / Tor Support** (SOCKS5 / HTTP with authentication)
- 💾 **SQLite Database** with rich metadata (views, forwards, replies, etc.)
- 📊 **Beautiful Rich CLI** (progress bars, tables, panels)
- ⚡ Robust **FloodWait** handling + automatic retries
- 🔗 Join public channels
- 📈 Database statistics command
- ⚙️ `.env` + CLI configuration

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/AnuragRoy485/Telegram-OSINT-Toolkit.git
cd Telegram-OSINT-Toolkit
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Credentials
```bash
cp config.example.env .env
```

Edit `.env`:
```env
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
```

Get your free API credentials from: [https://my.telegram.org](https://my.telegram.org) → API development tools.

---

## 📖 Usage

### Basic Search
```bash
python telegram_osint.py search @durov "telegram" --limit 50
```

### Bulk Search (Recommended for Intelligence Work)
```bash
python telegram_osint.py bulk-search channels.txt "malware OR APT36 OR ransomware" --limit 100 --since 2025-01-01 --output intel_report.json
```

### Full Chat Export
```bash
# JSON
python telegram_osint.py export @channel --limit 2000 --format json

# HTML report + media + links
python telegram_osint.py export @channel --limit 1500 --format html --media --links
```

### Enumerate Members
```bash
python telegram_osint.py members @groupname --limit 500
```

### User / Channel Profile
```bash
python telegram_osint.py profile @username
```

### Live Monitoring
```bash
# Monitor forever with keyword alerts
python telegram_osint.py monitor @channel1 @channel2 --keywords ransomware,APT,zero-day

# Monitor for 1 hour
python telegram_osint.py monitor @channel --keywords malware --duration 3600
```

### Join a Public Channel
```bash
python telegram_osint.py join @publicchannel
```

### Database Statistics
```bash
python telegram_osint.py stats
```

### Using Proxy / Tor
```bash
python telegram_osint.py --proxy socks5://127.0.0.1:9050 bulk-search channels.txt "keyword"
python telegram_osint.py --proxy socks5://user:pass@1.2.3.4:1080 search @channel "query"
```

---

## 📁 Project Structure

```
Telegram-OSINT-Toolkit/
├── telegram_osint.py          # Main advanced script
├── requirements.txt
├── config.example.env
├── channels.example.txt
├── .gitignore
├── README.md
├── media_*/                   # Auto-created media folders
└── telegram_osint.db          # SQLite database (auto-created)
```

---

## 🛠️ Requirements

```txt
telethon>=1.36.0
rich>=13.0
python-dotenv>=1.0.0
python-socks[asyncio]>=2.4.0
```

---

## ⚠️ Important Notes

- Always use dedicated accounts for heavy scraping.
- Respect rate limits — the tool already includes delays and FloodWait handling.
- For maximum OPSEC use Tor (`socks5://127.0.0.1:9050`) or a residential proxy.
- Only scrape data you are legally authorized to access.
- Large exports can take time and consume disk space (especially with `--media`).

---

## 📜 License

This project is licensed under the **MIT License**.

---

## 👤 Author

**Anurag Roy**  
Security Researcher | B.Tech CSE (AI) @ Techno India University  
GitHub: [@AnuragRoy485](https://github.com/AnuragRoy485)

---

⭐ **Star** this repository if you find it useful!  
🍴 Feel free to **Fork** and contribute improvements.

For feature requests, bug reports, Docker + Tor setup, AI analysis integration, or custom intelligence pipelines — open an **Issue** or **Pull Request**.
```
