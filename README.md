# OpenDesk 🪟🤖📱

OpenDesk is a **lite, free, open-source alternative** to conventional remote desktop applications, powered entirely by a local Large Language Model (like Ollama's Qwen, Llama, or Mistral) and controlled via Telegram.

## Features
- **Zero Subscriptions**: Uses strictly local Ollama models. Totally free.
- **Natural Language Control**: Tell your computer what to do ("Take a screenshot", "Create a docx about AI", "Open YouTube on Chrome").
- **Real File & System Control**: Terminal access, file read/write operations, Excel/Word generation.
- **GUI Automation**: Can click, type, and read the browser using Selenium and PyAutoGUI.
- **Easy connection**: Start the app in your CLI and immediately scan the generated QR Code to open Telegram on your phone.

## Prerequisites
1. **Python 3.11+**
2. **Ollama**: [Install Ollama](https://ollama.com/) and download a model (e.g. `ollama run qwen2.5`).
3. **Telegram Bot Token**: Create a bot using [BotFather](https://t.me/BotFather) on Telegram and copy the HTTP API Token.

## Setup Instructions

1. **Clone/Download** this repository.
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment**:
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and paste your Telegram Bot Token:
   ```env
   BOT_TOKEN=your_token_here
   OLLAMA_MODEL_NAME=qwen2.5
   OLLAMA_HOST=http://localhost:11434
   ```

## Running the App

Run the main Python module from the project root:
```bash
python -m opendesk.main
```

- A QR Code will appear in your terminal.
- Scan the QR code with your phone's camera to instantly open your bot in Telegram.
- Send a prompt like:
  - "Take a screenshot of my screen."
  - "What files are on my desktop?"
  - "Open browser and go to https://news.ycombinator.com"

## Security Warning
This application grants remote execution capabilities via Telegram. Never share your Bot Token, and consider restricting the Telegram bot to specifically respond only to your Chat ID for enhanced safety in a production environment.
