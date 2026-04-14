import os
from loguru import logger

from telegram import Update # type: ignore
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes # type: ignore

from opendesk.config import BOT_TOKEN, ALLOWED_TELEGRAM_ID, GROQ_API_KEY_2 # type: ignore
from opendesk.semantic_router import get_routing_info # type: ignore
from opendesk.core.simple_memory import simple_memory # type: ignore
from langchain_groq import ChatGroq
import asyncio
from typing import Dict
from datetime import datetime
import psutil

# Global state trackers
from opendesk.core.task_manager import task_manager # type: ignore
USER_PAUSED_STATE: Dict[int, bool] = {}

# Human-in-the-loop: pending confirmation actions per chat_id
# Supports two modes:
#   type="confirm"         → simple YES/NO gate
#   type="whatsapp_share"  → contact selection with optional screenshot
PENDING_ACTIONS: Dict[int, dict] = {}

# Track who is waiting for PIN
pending_pin_verification = {}

# Track failed attempts
failed_pin_attempts = {}

def _update_env(key: str, value: str):
    env_path = ".env"
    lines = []
    found = False
    
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()
    
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    
    if not found:
        new_lines.append(f"{key}={value}\n")
    
    with open(env_path, "w") as f:
        f.writelines(new_lines)

async def handle_pin_input(update, context, text, chat_id, user_id):
    pin = os.getenv("OPENDESK_PIN", "")
    
    if not pin:
        return False
    
    # Check if user is in PIN verification
    if chat_id not in pending_pin_verification:
        return False
    
    # Track failed attempts
    attempts = failed_pin_attempts.get(chat_id, 0)
    
    if attempts >= 3:
        await update.message.reply_text(
            "🚫 Too many wrong attempts!\n"
            "Wait 5 minutes and try again."
        )
        return True
    
    if text.strip() == pin:
        # PIN correct! Create a persistent owner session so all commands work.
        del pending_pin_verification[chat_id]
        failed_pin_attempts[chat_id] = 0
        
        from opendesk.utils.session_manager import get_session_by_user, create_owner_session
        if not get_session_by_user(user_id):
            create_owner_session(user_id)
        
        if not hasattr(task_manager, 'user_history'):
            task_manager.user_history = {}
        task_manager.user_history[chat_id] = []
        
        mode = os.getenv("USER_MODE", "local").upper()
        await update.message.reply_text(
            f"✅ PIN correct!\n"
            f"🖥️ Connected in {mode} mode!\n"
            f"👤 ID: {user_id}\n"
            f"Send commands now. 🚀"
        )
        return True
    else:
        # PIN wrong
        failed_pin_attempts[chat_id] = attempts + 1
        remaining = 3 - (attempts + 1)
        
        await update.message.reply_text(
            f"❌ Wrong PIN!\n"
            f"{remaining} attempts remaining."
        )
        return True

def set_pending_action(
    chat_id: int,
    action_description: str,
    original_command: str,
    action_type: str = "confirm",
    screenshot_path: str = None,
    file_name: str = None,
    contact_name: str = None,
    found_contacts: list = None,
):
    """Register a pending action requiring user confirmation or contact selection."""
    PENDING_ACTIONS[chat_id] = {
        "type": action_type,
        "action": action_description,
        "original_command": original_command,
        "screenshot_path": screenshot_path,
        "file_name": file_name,
        "contact_name": contact_name,
        "found_contacts": found_contacts or [],
    }

def set_whatsapp_contact_selection(
    chat_id: int,
    contact_name: str,
    filename: str,
    file_path: str,
    whatsapp_path: str,
    found_contacts: list = None,
):
    """Register a pending WhatsApp contact selection and send a formatted text list to the user."""
    import asyncio

    contacts = found_contacts or [contact_name]

    PENDING_ACTIONS[chat_id] = {
        "type": "whatsapp_share",
        "contact_name": contact_name,
        "filename": filename,
        "file_path": file_path,
        "whatsapp_path": whatsapp_path,
        "found_contacts": contacts,
    }
    logger.info(f"WhatsApp contact selection pending for chat {chat_id}: '{contact_name}' — {len(contacts)} match(es)")

    # Build a clean, numbered contact list message
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    contact_lines = "\n".join(
        f"{number_emojis[i] if i < len(number_emojis) else f'{i+1}.'} {name}"
        for i, name in enumerate(contacts)
    )

    if len(contacts) == 1:
        message = (
            f"📲 *WhatsApp — Contact Found*\n\n"
            f"I found this contact for *'{contact_name}'*:\n\n"
            f"1️⃣ {contacts[0]}\n\n"
            f"📎 File: `{filename}`\n\n"
            f"Reply *1* to confirm and send, or *cancel* to abort."
        )
    else:
        message = (
            f"📲 *WhatsApp — Multiple Contacts Found*\n\n"
            f"I found *{len(contacts)}* contacts matching *'{contact_name}'*:\n\n"
            f"{contact_lines}\n\n"
            f"📎 File: `{filename}`\n\n"
            f"Reply with the *number* (1, 2, 3...) of the correct contact,\n"
            f"or *cancel* to abort."
        )

    # Send the text message asynchronously — no photo upload, instant delivery
    async def _send_text():
        try:
            from telegram import Bot
            from opendesk.config import BOT_TOKEN
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send WhatsApp contact list message: {e}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_send_text())
        else:
            loop.run_until_complete(_send_text())
    except Exception as e:
        logger.error(f"Could not schedule WhatsApp contact message: {e}")




INSTANT_REPLIES = {
    # Greetings
    "hello": "Hey! OpenDesk here! How can I help?",
    "hi": "Hey! OpenDesk here! How can I help?",
    "hey": "Hey! OpenDesk here! How can I help?",
    
    # Thanks
    "thankyou": "You're welcome! 😊 Anything else?",
    "thank you": "You're welcome! 😊 Anything else?",
    "thanks": "You're welcome! 😊 Anything else?",
    "thnx": "You're welcome! 😊 Anything else?",
    "thx": "You're welcome! 😊 Anything else?",
    "ty": "You're welcome! 😊 Anything else?",
    
    # Acknowledgements
    "ok": "Got it! 👍 Send next command.",
    "okay": "Got it! 👍 Send next command.",
    "ok thanks": "You're welcome! 😊",
    "ok thankyou": "You're welcome! 😊",
    "noted": "Got it! 👍",
    "got it": "Great! 😊 What's next?",
    "done": "Awesome! ✅ What's next?",
    "nice": "Glad it worked! 😊",
    "good": "Great! 😊 Anything else?",
    "great": "Awesome! 🎉 What's next?",
    "perfect": "Great! 😊 What's next?",
    "awesome": "Glad to help! 🙌",
    "wow": "😊 What can I do next?",
    "cool": "😎 What's next?",
    
    # Goodbye
    "bye": "Goodbye! 👋 Come back anytime!",
    "goodbye": "Goodbye! 👋 Take care!",
    "see you": "See you! 👋",
    "cya": "See you! 👋",
    
    # How are you
    "how are you": "All systems running perfectly! ⚡",
    "how r u": "All systems running perfectly! ⚡",
    "whats up": "Ready to help! ⚡ What do you need?",
    "sup": "Ready! ⚡ What do you need?",
    
    # What can you do
    "what can you do": (
        "I can control your laptop! Try:\n"
        "• open chrome\n"
        "• set volume to 50\n"
        "• take a screenshot\n"
        "• share a file\n"
        "• play music on spotify"
    ),
}

TIME_PATTERNS = [
    "what time is it",
    "what time it is", 
    "what is the time",
    "time please",
    "current time",
    "tell me time",
]

BATTERY_PATTERNS = [
    "battery level",
    "battery status",
    "how much battery",
]

STOP_WORDS = [
    "stop", "Stop", "STOP",
    "cancel", "Cancel", "CANCEL", 
    "abort", "Abort", "halt",
    "pause", "Pause", "exit",
    "/stop", "/cancel", "/abort"
]

RESUME_WORDS = [
    "resume", "Resume", "continue",
    "go", "start", "/resume", "/start"
]

from opendesk.db.crud import get_all_screenshots, get_screenshot_by_id
from opendesk.utils.session_manager import get_session_by_user, claim_session, disconnect_session, is_session_valid

def is_authorized(user_id: int) -> bool:
    """Checks if the user is authorized to interact with the bot."""
    if ALLOWED_TELEGRAM_ID is None:
        logger.warning(f"Unauthorized access attempt by {user_id}. ALLOWED_TELEGRAM_ID is NOT set in .env!")
        return False
    return user_id == ALLOWED_TELEGRAM_ID

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answers the `/start` command and processes session tokens."""
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ Unauthorized. Your Telegram ID is not on the whitelist.")
        return
    
    args = context.args
    
    # If token provided validate it
    if args and len(args) > 0:
        token = args[0]
        if is_session_valid(token):
            claim_session(token, user_id)
            
            if not hasattr(task_manager, 'user_history'):
                task_manager.user_history = {}
            task_manager.user_history[chat_id] = []
            
            # Check PIN
            pin = os.getenv("OPENDESK_PIN", "")
            if pin:
                pending_pin_verification[chat_id] = "start"
                await update.message.reply_text("🔐 Enter your PIN to connect:")
                return
            
            mode = os.getenv("USER_MODE", "local").upper()
            await update.message.reply_text(
                f"✅ Connected in {mode} mode!\n"
                f"👤 ID: {user_id}\n"
                f"Send commands now."
            )
            return
    
    # No token - owner connects directly!
    # Owner does not need QR code ever!
    from opendesk.utils.session_manager import get_session_by_user, create_owner_session
    
    # Ensure owner has a registered session so all commands work
    if not get_session_by_user(user_id):
        create_owner_session(user_id)

    pin = os.getenv("OPENDESK_PIN", "")
    if pin:
        pending_pin_verification[chat_id] = "start"
        await update.message.reply_text("🔐 Enter your PIN to connect:")
        return
    
    # Connect directly
    if not hasattr(task_manager, 'user_history'):
        task_manager.user_history = {}
    task_manager.user_history[chat_id] = []
    
    mode = os.getenv("USER_MODE", "local").upper()
    await update.message.reply_text(
        f"✅ Connected in {mode} mode!\n"
        f"👤 ID: {user_id}\n"
        f"Send commands now."
    )

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        return

    session = get_session_by_user(user_id)
    
    if not session:
        await update.message.reply_text(
            "🔴 Not connected.\n"
            "Send /start to connect (PIN required if set)."
        )
        return
        
    import time
    active_since = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session["created_at"]))
    
    active_since = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session["created_at"]))
    mode = os.getenv("USER_MODE", "local").upper()
    
    await update.message.reply_text(
        f"🟢 **Status:** Connected\n"
        f"⚙️ **Mode:** {mode}\n"
        f"💻 **Laptop ID:** `{session['laptop_id']}`\n"
        f"👤 **Admin ID:** `{user_id}`\n"
        f"⏱️ **Active Since:** {active_since}\n"
        f"🔗 **Connection:** Active"
    )

async def disconnect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        return
        
    if disconnect_session(user_id):
        await update.message.reply_text("🔌 Disconnected from laptop.")
    else:
        await update.message.reply_text("You are not currently connected.")

async def screenshots_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists recent screenshots from the database."""
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        return
        
    if not get_session_by_user(user_id):
        await update.message.reply_text("⚠️ Not connected.")
        return
        
    shots = get_all_screenshots()
    if not shots:
        await update.message.reply_text("📸 No screenshots found in database.")
        return
        
    # Show last 10
    msg = "📸 **Your screenshots:**\n"
    for s in shots[:10]:
        # Format: ID. Time - Context
        msg += f"{s['id']}. {s['timestamp']} - {s['context_description']}\n"
    
    msg += "\nType `/getscreenshot <id>` to receive one."
    await update.message.reply_text(msg, parse_mode='Markdown')

async def getscreenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retrieves a specific screenshot by ID and sends it."""
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        return
        
    if not get_session_by_user(user_id):
        await update.message.reply_text("⚠️ Not connected.")
        return
        
    if not context.args:
        await update.message.reply_text("Usage: `/getscreenshot <id>`")
        return
        
    try:
        shot_id = int(context.args[0])
        shot = get_screenshot_by_id(shot_id)
        if not shot:
            await update.message.reply_text(f"❌ Screenshot ID {shot_id} not found.")
            return
            
        file_path = shot['file_path']
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                await update.message.reply_photo(photo=f, caption=f"Screenshot #{shot_id}\nCaptured: {shot['timestamp']}")
        else:
            await update.message.reply_text(f"❌ File not found on disk at `{file_path}`")
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid numeric ID.")
    except Exception as e:
        logger.error(f"Error in getscreenshot: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def reconnect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    # Check if PIN is set
    pin = os.getenv("OPENDESK_PIN", "")
    if pin:
        # Ask for PIN
        pending_pin_verification[chat_id] = "reconnect"
        await update.message.reply_text("🔐 Enter your PIN to connect:")
        return
    
    # No PIN - connect directly
    from opendesk.utils.session_manager import get_session_by_user, create_owner_session
    if not get_session_by_user(user_id):
        create_owner_session(user_id)

    if not hasattr(task_manager, 'user_history'):
        task_manager.user_history = {}
    task_manager.user_history[chat_id] = []
    
    await update.message.reply_text(
        "🔄 Reconnected successfully!\n"
        "✅ Send commands now."
    )

async def changepin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: /changepin NEWPIN\n"
            "Example: /changepin 5678"
        )
        return
    
    new_pin = context.args[0]
    
    if not new_pin.isdigit():
        await update.message.reply_text("❌ PIN must be numbers only!")
        return
    
    if len(new_pin) < 4:
        await update.message.reply_text("❌ PIN must be at least 4 digits!")
        return
    
    # Save to .env
    _update_env("OPENDESK_PIN", new_pin)
    
    await update.message.reply_text(
        f"✅ PIN updated successfully!\n"
        f"New PIN: {'*' * len(new_pin)}"
    )

async def apps_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows all indexed apps from the AppIndexer."""
    user_id = update.message.from_user.id if hasattr(update.message, 'from_user') else None
    if not is_authorized(user_id):
        return
        
    if not get_session_by_user(user_id):
        await update.message.reply_text("⚠️ Not connected.")
        return
        
    from opendesk.utils.app_indexer import app_indexer
    
    if app_indexer.is_indexing:
        await update.message.reply_text("⏳ App indexer is currently running in the background. Please wait a moment.")
        return
        
    apps = app_indexer.get_all_apps()
    
    if not apps:
        await update.message.reply_text("❌ No apps found in the index yet.")
        return
        
    total_apps = len(apps)
    display_limit = 10
    
    # Sort and pick top apps (mostly to show common ones first if possible, or just alphabetical)
    apps.sort(key=lambda x: x["app_name"])
    
    msg = f"📱 **Installed Apps** ({total_apps} found):\n"
    for app in apps[:display_limit]:
        msg += f"• {app['app_name'].title()} → Ready\n"
        
    if total_apps > display_limit:
        msg += f"... and {total_apps - display_limit} more"
        
    await update.message.reply_text(msg, parse_mode='Markdown')

async def stop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for /cancel"""
    await cancel_handler(update, context)

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any running agent task and clears the queue for this chat."""
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        return
        
    chat_id = update.message.chat_id
    
    # 1. Clear the queue
    from opendesk.core.simple_memory import simple_memory
    if chat_id in simple_memory.history: # Using as proxy for user known to bot
        while not task_manager.queue.empty():
            try:
                task_manager.queue.get_nowait()
                task_manager.queue.task_done()
            except asyncio.QueueEmpty:
                break
    
    # 2. Cancel current task in TaskManager
    cancelled = await task_manager.cancel_current_task()
    if cancelled:
        await update.message.reply_text("🛑 Task cancelled and queue cleared!")
    else:
        await update.message.reply_text("ℹ️ No active command to cancel.")
    
    # Reset paused state always on cancel to ensure responsiveness
    USER_PAUSED_STATE[chat_id] = False

async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Bug 1: Context Aware Resume. Checks history for music context."""
    # Check last command in history
    history = simple_memory.get_context(chat_id, limit=5)
    
    last_user_commands = [
        msg["content"].lower()
        for msg in history
        if msg["role"] == "user"
    ]
    
    MUSIC_KEYWORDS = [
        "music", "song", "spotify",
        "play", "pause", "track",
        "audio", "volume"
    ]
    
    # Was last command music related?
    music_context = any(
        any(kw in cmd for kw in MUSIC_KEYWORDS)
        for cmd in last_user_commands
    )
    
    if music_context:
        logger.info(f"Music context detected for resume in chat {chat_id}")
        # Resume music not just connection!
        await task_manager.add_to_queue(
            update, context,
            "resume the music on spotify"
        )
        # Also ensure connection is resumed
        USER_PAUSED_STATE[chat_id] = False
    else:
        # No music context = standard connection resume
        USER_PAUSED_STATE[chat_id] = False
        try:
            await update.message.reply_text("✅ Ready for commands!", read_timeout=30, write_timeout=30)
        except Exception as e:
            logger.warning(f"Failed to send resume text (network error): {e}")

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Bug 2: Fast LLM fallback for unknown commands using Groq."""
    chat_id = update.message.chat_id
    history = simple_memory.get_context(chat_id, limit=3)
    
    context_text = "\n".join([
        f"{m['role']}: {m['content']}"
        for m in history
    ])
    
    prompt = f"""Previous conversation:
{context_text}

User now says: {text}

You are OpenDesk AI assistant.
Reply helpfully based on context.
If user said check again or verify, check if the last task worked.
Be concise and friendly."""
    
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        groq_api_key=GROQ_API_KEY_2,
        temperature=0.7,
        max_tokens=150
    )
    
    logger.info(f"Routing unknown command to fast LLM: '{text}'")
    try:
        response = await llm.ainvoke(prompt)
        reply = response.content
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Fast LLM chat failed: {e}")
        await update.message.reply_text("Could you rephrase that? I want to help! 😊")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for incoming text: Routes to immediate execution or the command queue."""
    text = update.message.text
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    
    if not text or not is_authorized(user_id):
        return
    
    text_lower = text.lower().strip()
    
    # PRIORITY 1: Check STOP/CANCEL (Highest Priority)
    if text_lower in [w.lower() for w in STOP_WORDS]:
        await cancel_handler(update, context)
        USER_PAUSED_STATE[chat_id] = False
        return

    # PRIORITY 2: Check PIN input next
    pin_handled = await handle_pin_input(
        update, context, text,
        chat_id, user_id
    )
    if pin_handled:
        return


    # PRIORITY 3: Check INSTANT REPLIES (exact or near-exact full message only)
    from thefuzz import fuzz
    for key in INSTANT_REPLIES:
        if text_lower == key or fuzz.ratio(text_lower, key) > 90:
            await update.message.reply_text(INSTANT_REPLIES[key])
            return

    # PRIORITY 4: TIME / BATTERY / VOLUME (Hardcoded Quick Response)
    TIME_WORDS = ["time", "what time", "current time", "time is it", "time it is", "kitna baja", "baje hain"]
    BATTERY_WORDS = ["battery", "charge", "kitni battery"]

    if any(w in text_lower for w in TIME_WORDS):
        now = datetime.now().strftime("%I:%M %p")
        await update.message.reply_text(f"🕐 Current time: {now}")
        return

    if any(w in text_lower for w in BATTERY_WORDS):
        battery = psutil.sensors_battery()
        if battery:
            plugged = "🔌 Charging" if battery.power_plugged else "🔋 On battery"
            await update.message.reply_text(f"🔋 Battery: {battery.percent:.0f}%\n{plugged}")
        else:
            await update.message.reply_text("🔋 Battery information not available.")
        return

    # PRIORITY 5: CONTEXT AWARE RESUME
    if text_lower in [w.lower() for w in RESUME_WORDS]:
        await handle_resume(update, context, chat_id)
        return

    if USER_PAUSED_STATE.get(chat_id, False):
        return

    # PRIORITY 5.5: Human-in-the-loop confirmation handler (remains critical)
    if chat_id in PENDING_ACTIONS:
        pending = PENDING_ACTIONS[chat_id]
        is_yes = text_lower in ["yes", "y", "haan", "ha", "confirm", "ok", "okay"]
        is_no  = text_lower in ["no", "n", "nahi", "nope", "cancel", "stop", "abort"]

        if pending.get("type") == "whatsapp_share":
            is_cancel = text_lower in ["no", "n", "nahi", "cancel", "stop", "abort"]
            if is_cancel:
                del PENDING_ACTIONS[chat_id]
                await update.message.reply_text("❌ WhatsApp file send cancelled.")
                return
            # Expect a number like "1", "2" etc.
            if text_lower.strip().isdigit():
                contact_index = int(text_lower.strip()) - 1  # Convert to 0-based index
                p = PENDING_ACTIONS.pop(chat_id)
                await update.message.reply_text(
                    f"📤 Sending *{p['filename']}* to contact #{contact_index + 1}...",
                    parse_mode="Markdown"
                )
                try:
                    from opendesk.tools.system import _do_whatsapp_file_send
                    result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: _do_whatsapp_file_send(
                            contact_name=p["contact_name"],
                            file_path=p["file_path"],
                            whatsapp_path=p["whatsapp_path"],
                            contact_index=contact_index,
                        )
                    )
                    await update.message.reply_text(result)
                except Exception as e:
                    await update.message.reply_text(f"❌ Failed to send: {e}")
                return
            else:
                await update.message.reply_text(
                    "⚠️ Please reply with a **number** (e.g. 1, 2, 3) to pick the contact, "
                    "or **cancel** to abort.",
                    parse_mode="Markdown"
                )
                return

        if pending.get("type") == "confirm":
            if is_yes:
                del PENDING_ACTIONS[chat_id]
                await update.message.reply_text("✅ Confirmed! Proceeding...")
                approved_command = f"[USER CONFIRMED] {pending['original_command']}"
                await task_manager.add_to_queue(update, context, approved_command)
                return
            elif is_no:
                del PENDING_ACTIONS[chat_id]
                await update.message.reply_text("❌ Cancelled. Action aborted.")
                return
            else:
                await update.message.reply_text(
                    f"⚠️ Waiting for confirmation:\n`{pending['action']}`\n\n"
                    f"Reply **YES** to proceed or **NO** to cancel.",
                    parse_mode="Markdown"
                )
                return

    # PRIORITY 6: CLASSIFY INTENT (Laptop command vs General chat)
    # Use Semantic Router to decide if we need the heavy agent pipeline
    routing = await get_routing_info(text)
    if routing["level"] in ["simple", "medium", "complex"]:
        logger.info(f"Intent classified as LAPTOP COMMAND ({routing['level']}). Queuing for agent.")
        await task_manager.add_to_queue(update, context, text)
        return

    # PRIORITY 7: UNKNOWN -> Fast General Chat
    logger.info(f"Intent classified as GENERAL. Routing to fast LLM fallback.")
    await handle_unknown(update, context, text)

async def post_init(application):
    """Start the global TaskManager queue processor."""
    task_manager.processor_task = asyncio.create_task(task_manager.start_queue_processor())
    from opendesk.main import send_startup_notification
    await send_startup_notification(application.bot)

async def post_stop(application):
    """Cleanly cancel the background queue processor."""
    if task_manager.processor_task:
        task_manager.processor_task.cancel()
        try:
            await task_manager.processor_task
        except asyncio.CancelledError:
            logger.debug("TaskManager queue processor stopped cleanly.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a message pointing to the logs."""
    if context.error:
        logger.error(f"Exception while handling an update: {context.error}")
        import traceback
        traceback.print_exception(type(context.error), context.error, context.error.__traceback__)
    else:
        logger.error("Exception while handling an update: (No error context)")

def run_bot():
    """Starts the long-polling Telegram bot."""
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN provided, cannot start bot.")
        return

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)   # Allow 30s to establish connection (fixes ConnectTimeout)
        .read_timeout(60.0)      # Allow 60s for long-running responses
        .write_timeout(30.0)     # Allow 30s for sending messages
        .pool_timeout(30.0)      # Allow 30s to get a connection from the pool
        .post_init(post_init)
        .post_stop(post_stop)
        .build()
    )

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("disconnect", disconnect_handler))
    app.add_handler(CommandHandler("cancel", cancel_handler))
    app.add_handler(CommandHandler("stop", stop_handler))
    app.add_handler(CommandHandler("screenshots", screenshots_handler))
    app.add_handler(CommandHandler("getscreenshot", getscreenshot_handler))
    app.add_handler(CommandHandler("apps", apps_handler))
    app.add_handler(CommandHandler("reconnect", reconnect_handler))
    app.add_handler(CommandHandler("changepin", changepin_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    app.add_error_handler(error_handler)

    logger.debug("Bot is polling. Press Ctrl+C to stop.")
    app.run_polling()
