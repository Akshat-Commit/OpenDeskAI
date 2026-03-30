# 🖥️ OpenDesk AI

> Your Laptop. Your Phone. No Limits.

[Badges: Stars, License, Python, Issues]

## What is OpenDesk?
Free open source AI agent that controls
your Windows laptop via Telegram.
Alternative to Claude Remote Control
but completely free.

## ✨ Features
- 🤖 Multi-model AI fallback chain
- 📁 Smart file indexing and sharing
- 🌐 Playwright browser automation
- 🔍 DuckDuckGo web search
- 📱 WhatsApp file sharing
- 🎵 Spotify control
- 📸 Screenshot with OCR search
- 🔒 PIN security system
- 🚀 One command setup
- 💾 SQLite persistent memory
- 👁️ Vision AI with Moondream
- 🌍 Works from anywhere via QR

## 📋 Requirements
- Windows 10/11
- Python 3.10+
- Telegram account
- 8GB+ RAM recommended

## 🚀 Quick Start
pip install opendesk
opendesk setup
opendesk start

## ⚙️ CLI Commands
opendesk setup    → First time setup
opendesk start    → Start + QR code
opendesk stop     → Stop bot
opendesk status   → Health check
opendesk config   → Change settings
opendesk logs     → View logs
opendesk version  → Version info

## 🔒 Security
- Telegram ID whitelist
- Optional PIN protection
- All data stays on your laptop
- No central server

## 🏗️ Tech Stack
| Layer | Technology |
|-------|-----------|
| AI Engine | LangChain + Ollama |
| Cloud AI | Groq + Gemini + GitHub |
| Vision | Moondream |
| Bot | python-telegram-bot |
| Browser | Playwright |
| Search | DuckDuckGo |
| Tunnel | Cloudflare |
| Database | SQLite |
| Logging | Loguru |
| CLI | Typer + Rich |
| Process | PM2 |

## 📁 Project Structure
OpenDeskAI/
├── opendesk/
│   ├── main.py
│   ├── bot.py
│   ├── cli.py
│   ├── agent.py
│   ├── config.py
│   ├── setup_wizard.py
│   ├── semantic_router.py
│   ├── health_check.py
│   ├── ollama_agent/
│   │   ├── langchain_agent.py
│   │   ├── judge_agent.py
│   │   └── memory_agent.py
│   ├── tools/
│   │   ├── filesystem.py
│   │   ├── browser.py
│   │   ├── system.py
│   │   ├── terminal.py
│   │   ├── app_launcher.py
│   │   ├── clipboard.py
│   │   ├── office.py
│   │   └── schemas.py
│   ├── core/
│   │   ├── task_manager.py
│   │   └── simple_memory.py
│   ├── db/
│   │   ├── connection.py
│   │   └── crud.py
│   └── utils/
│       ├── banner.py
│       ├── file_indexer.py
│       ├── app_indexer.py
│       ├── path_detector.py
│       ├── ocr_analyzer.py
│       ├── qr_generator.py
│       └── context_monitor.py
├── tests/
├── data/
├── logs/
├── .env.example
├── setup.py
├── requirements.txt
└── README.md

## ❓ FAQ

Q: Does it work without internet?
A: Partially. Telegram needs internet.
   AI runs locally via Ollama.

Q: Is it free?
A: 100% free and open source forever.

Q: Which AI model should I use?
A: llama3.1:8b for local mode.
   Groq llama-3.3-70b for cloud mode.

Q: Does it work on Mac or Linux?
A: Windows only for now.

## 🤝 Contributing
Contributions welcome!
See CONTRIBUTING.md for guidelines.

## 📄 License
MIT License - free to use forever.

---
Made with ❤️ by Akshat Jain
