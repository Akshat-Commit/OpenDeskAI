import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot

load_dotenv("c:/Users/AKSHAT JAIN/OneDrive/Desktop/OpenDeskAI/.env")

async def test_bot():
    token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("ALLOWED_TELEGRAM_ID")
    print(f"Token: {token[:10]}... Chat ID: {chat_id}")
    
    bot = Bot(token=token)
    try:
        await bot.send_message(chat_id=chat_id, text="🧪 Diagnostic Test: Bot is connected to Telegram!")
        print("SUCCESS! Message sent.")
    except Exception as e:
        print(f"FAILED! Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_bot())
