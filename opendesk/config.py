# opendesk config and settings
import os
from pathlib import Path
from dotenv import load_dotenv # type: ignore

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
GROQ_API_KEY_1 = os.getenv("GROQ_API_KEY_1", os.getenv("GROQ_API_KEY", ""))
GROQ_API_KEY_2 = os.getenv("GROQ_API_KEY_2", "")
GROQ_API_KEY_3 = os.getenv("GROQ_API_KEY_3", "")
GROQ_API_KEY = GROQ_API_KEY_1 # Default alias
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GITHUB_API_KEY = os.getenv("GITHUB_API_KEY", "")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "gemma3:4b")
OLLAMA_VISION_MODEL_NAME = os.getenv("OLLAMA_VISION_MODEL_NAME", "moondream")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# User mode: "developer", "local", or "cloud" (set by setup_wizard or .env)
USER_MODE = os.getenv("USER_MODE", "local").strip().lower()

# Environment: "production" or "testing"
OPENDESK_ENV = os.getenv("OPENDESK_ENV", "production").strip().lower()

# Security: Allowed Telegram User ID for command execution
_allowed_id = os.getenv("ALLOWED_TELEGRAM_ID", "")
ALLOWED_TELEGRAM_ID = int(_allowed_id) if _allowed_id.isdigit() else None

# DB Settings
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "opendesk.db")

# Basic validation
if not BOT_TOKEN:
    print("WARNING: BOT_TOKEN is not set in the environment or .env file.")

