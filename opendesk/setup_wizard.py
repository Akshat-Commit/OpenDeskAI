"""
OpenDesk First-Run Setup Wizard & Developer Detection.

Handles three user modes:
- developer: Full fallback chain, auto-detected from .env
- local: Ollama-powered, 100% offline
- cloud: Groq-powered, needs free API key
"""
import os
import psutil  # type: ignore
import subprocess
from loguru import logger
from dotenv import load_dotenv, set_key  # type: ignore


ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

# ──────────────────────────────────────────────
#  Developer Detection
# ──────────────────────────────────────────────

def detect_user_mode() -> str | None:
    """
    Returns 'developer' if .env already has 2+ premium API keys.
    Returns the stored USER_MODE if already configured.
    Returns None if first-run (wizard needed).
    """
    load_dotenv(ENV_PATH, override=True)

    stored_mode = os.getenv("USER_MODE", "").strip().lower()
    if stored_mode in ("developer", "local", "cloud"):
        return stored_mode

    # Count how many premium keys exist
    keys_present = 0
    for key_name in ("GROQ_API_KEY_1", "GROQ_API_KEY_2", "GEMINI_API_KEY", "GITHUB_API_KEY"):
        val = os.getenv(key_name, "").strip()
        if val and not val.startswith("your_"):
            keys_present += 1

    if keys_present >= 2:
        # Auto-save so wizard never triggers again
        set_key(ENV_PATH, "USER_MODE", "developer")
        return "developer"

    return None


# ──────────────────────────────────────────────
#  RAM Detection for LOCAL mode
# ──────────────────────────────────────────────

def _get_ram_gb() -> float:
    """Returns total system RAM in GB."""
    return psutil.virtual_memory().total / (1024 ** 3)


def _suggest_ollama_model() -> str | None:
    """Suggests an Ollama model based on RAM. Returns None if <8GB and user declines."""
    ram_gb = _get_ram_gb()

    if ram_gb >= 16:
        model = "gemma3:12b"
        print(f"\n💾 Detected {ram_gb:.0f} GB RAM → Using gemma3:12b (best quality)")
    elif ram_gb >= 8:
        model = "gemma3:4b"
        print(f"\n💾 Detected {ram_gb:.0f} GB RAM → Using gemma3:4b (lightweight)")
    else:
        print(f"\n⚠️  Your laptop has {ram_gb:.0f} GB RAM.")
        print("   LOCAL mode may be very slow.")
        print("   We recommend CLOUD mode instead.")
        choice = input("   Continue with LOCAL anyway? (y/n): ").strip().lower()
        if choice != "y":
            return None
        model = "gemma3:4b"

    return model


def _pull_ollama_model(model: str) -> bool:
    """Downloads the Ollama model. Returns True on success."""
    print(f"\n📥 Downloading {model} (this may take a few minutes)...\n")
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            timeout=600  # 10 minute timeout
        )
        if result.returncode == 0:
            print(f"\n✅ {model} downloaded successfully!")
            return True
        else:
            print(f"\n❌ Failed to download {model}.")
            return False
    except FileNotFoundError:
        print("\n❌ Ollama is not installed!")
        print("   Install it from: https://ollama.com/download")
        return False
    except subprocess.TimeoutExpired:
        print(f"\n❌ Download timed out for {model}.")
        return False


# ──────────────────────────────────────────────
#  CLOUD mode: Groq key validation
# ──────────────────────────────────────────────

def _validate_groq_key(api_key: str) -> bool:
    """Tests a Groq API key with a minimal request."""
    import requests
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
            },
            timeout=15,
        )
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            print("❌ Invalid API key. Please check and try again.")
            return False
        else:
            print(f"⚠️  Groq returned status {response.status_code}. Key may still work.")
            return True  # Might be rate-limited but key format is valid
    except Exception as e:
        print(f"⚠️  Could not verify key: {e}")
        print("   Saving anyway — you can test later.")
        return True


# ──────────────────────────────────────────────
#  Main Wizard
# ──────────────────────────────────────────────

def run_setup_wizard() -> str:
    """
    Interactive first-run wizard. Returns the chosen mode ('local' or 'cloud').
    Saves configuration to .env.
    """
    print("\n" + "=" * 50)
    print("  Welcome to OpenDesk!")
    print("=" * 50)
    print()
    print("  Choose your AI mode:")
    print()
    print("  1. 🏠 LOCAL (Recommended)")
    print("     - Works offline")
    print("     - 100% private")
    print("     - No API keys needed")
    print("     - Downloads AI model once")
    print()
    print("  2. ☁️  CLOUD (Faster)")
    print("     - Needs free Groq API key")
    print("     - Get it free at groq.com")
    print("     - Faster responses")
    print("     - Needs internet")
    print()

    while True:
        choice = input("  Enter choice (1 or 2): ").strip()
        if choice in ("1", "2"):
            break
        print("  Please enter 1 or 2.")

    if choice == "1":
        return _setup_local_mode()
    else:
        return _setup_cloud_mode()


def _setup_local_mode() -> str:
    """Configures LOCAL mode: detects RAM, pulls Ollama model, saves .env."""
    model = _suggest_ollama_model()

    if model is None:
        # User declined LOCAL with low RAM → redirect to CLOUD
        print("\n  Switching to CLOUD mode...\n")
        return _setup_cloud_mode()

    # Check Ollama is installed
    if not _pull_ollama_model(model):
        print("\n  ⚠️  Could not set up local mode.")
        print("  Falling back to CLOUD mode...\n")
        return _setup_cloud_mode()

    # Save to .env
    set_key(ENV_PATH, "USER_MODE", "local")
    set_key(ENV_PATH, "OLLAMA_MODEL_NAME", model)

    print("\n✅ LOCAL mode configured!")
    print(f"   Model: {model}")
    print("   Everything runs on your machine. Zero API keys needed.\n")
    logger.info(f"Setup wizard: LOCAL mode configured with {model}")
    return "local"


def _setup_cloud_mode() -> str:
    """Configures CLOUD mode: gets Groq key, validates, saves .env."""
    print("\n  Get your free API key at: https://console.groq.com/keys")
    print("  (Create a free account → Generate API Key → Copy it)\n")

    while True:
        api_key = input("  Enter your Groq API key: ").strip()
        if not api_key:
            print("  Key cannot be empty.")
            continue
        if not api_key.startswith("gsk_"):
            print("  ⚠️  Groq keys usually start with 'gsk_'. Are you sure?")
            confirm = input("  Continue anyway? (y/n): ").strip().lower()
            if confirm != "y":
                continue

        print("  🔍 Validating key...")
        if _validate_groq_key(api_key):
            break
        # If validation failed with 401, loop back to ask again

    # Save to .env
    set_key(ENV_PATH, "USER_MODE", "cloud")
    set_key(ENV_PATH, "GROQ_API_KEY_1", api_key)

    print("\n✅ CLOUD mode configured!")
    print("   Model: llama-3.3-70b-versatile")
    print("   500K tokens/day free. Enjoy! 🚀\n")
    logger.info("Setup wizard: CLOUD mode configured with Groq")
    return "cloud"
