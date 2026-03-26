import os
from loguru import logger

from telegram import Update # type: ignore
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes # type: ignore

from opendesk.config import BOT_TOKEN, ALLOWED_TELEGRAM_ID # type: ignore



import asyncio
from typing import Dict
from datetime import datetime
import psutil

# Global state trackers
from opendesk.core.task_manager import task_manager # type: ignore
USER_PAUSED_STATE: Dict[int, bool] = {}

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
    
    # Extract token if provided: `/start XYZ123`
    args = context.args
    if args and len(args) > 0:
        token = args[0]
        if is_session_valid(token):
            success = claim_session(token, user_id)
            if success:
                from opendesk.core.simple_memory import simple_memory
                simple_memory.history[chat_id] = []  # Fresh start for new session
                await update.message.reply_text("✅ Connected to your laptop! Send commands now.")
                return
            else:
                await update.message.reply_text("❌ Failed to claim session. Please try again.")
                return
        else:
            await update.message.reply_text("❌ QR code expired or invalid. Run `opendesk start` again on your laptop.")
            return

    # Normal starting text if no token provided or clicked randomly
    await update.message.reply_text(
        "🖥️ Welcome to OpenDesk!\n"
        "Please scan the QR code from your terminal to connect to your PC."
    )

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        return

    session = get_session_by_user(user_id)
    
    if not session:
        await update.message.reply_text("🔴 Not connected. Please scan a QR code from your laptop.")
        return
        
    import time
    active_since = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session["created_at"]))
    
    await update.message.reply_text(
        f"🟢 **Status:** Connected\n"
        f"💻 **Laptop ID:** `{session['laptop_id']}`\n"
        f"⏱️ **Active Since:** {active_since}\n"
        f"🔗 **Connection:** Active (Ngrok)"
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

async def apps_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows all indexed apps from the AppIndexer."""
    user_id = update.message.fromuser.id if hasattr(update.message, 'from_user') else update.message.from_user.id
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

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for incoming text: Routes to immediate execution or the command queue."""
    text = update.message.text
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    
    if not text:
        return
        
    if not is_authorized(user_id):
        return

    text_lower = text.lower().strip()
        
    # PRIORITY 1: Check STOP/RESUME (Instant)
    if text_lower in [w.lower() for w in STOP_WORDS]:
        await cancel_handler(update, context)
        # We set paused to False inside cancel_handler anyway, 
        # but the user might want a moment of silence or just a stop.
        # Following rule 5: set False immediately after cancel.
        USER_PAUSED_STATE[chat_id] = False
        return

    if text_lower in [w.lower() for w in RESUME_WORDS]:
        USER_PAUSED_STATE[chat_id] = False
        await update.message.reply_text("✅ Resumed! Ready for commands.")
        return

    if USER_PAUSED_STATE.get(chat_id, False):
        return

    # PRIORITY 2: Check INSTANT REPLIES (Fuzzy Match)
    from thefuzz import fuzz
    for key in INSTANT_REPLIES:
        if key == text_lower or key in text_lower or text_lower in key or fuzz.ratio(text_lower, key) > 85:
            await update.message.reply_text(INSTANT_REPLIES[key])
            return

    # PRIORITY 3: HARDCODED CHECK (0.1s Execution)
    TIME_WORDS = [
        "time", "what time", "current time",
        "time is it", "time it is",
        "kitna baja", "baje hain"
    ]

    BATTERY_WORDS = [
        "battery", "charge", "kitni battery"
    ]

    VOLUME_WORDS = [
        "volume", "sound level"
    ]

    if any(w in text_lower for w in TIME_WORDS):
        now = datetime.now().strftime("%I:%M %p")
        await update.message.reply_text(
            f"🕐 Current time: {now}"
        )
        return

    if any(w in text_lower for w in BATTERY_WORDS):
        battery = psutil.sensors_battery()
        if battery:
            plugged = "🔌 Charging" if battery.power_plugged else "🔋 On battery"
            await update.message.reply_text(
                f"🔋 Battery: {battery.percent:.0f}%\n{plugged}"
            )
        else:
            await update.message.reply_text("🔋 Battery information not available.")
        return

    if any(w in text_lower for w in VOLUME_WORDS):
        await update.message.reply_text(
            "🔊 Use: set volume to [0-100]"
        )
        return

    # PRIORITY 4: ENQUEUE IN TASKMANAGER
    await task_manager.add_to_queue(update, context, text)

async def post_init(application):
    """Start the global TaskManager queue processor."""
    task_manager.processor_task = asyncio.create_task(task_manager.start_queue_processor())

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
    logger.exception("Exception while handling an update:")

def run_bot():
    """Starts the long-polling Telegram bot."""
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN provided, cannot start bot.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).post_stop(post_stop).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("disconnect", disconnect_handler))
    app.add_handler(CommandHandler("cancel", cancel_handler))
    app.add_handler(CommandHandler("stop", stop_handler))
    app.add_handler(CommandHandler("screenshots", screenshots_handler))
    app.add_handler(CommandHandler("getscreenshot", getscreenshot_handler))
    app.add_handler(CommandHandler("apps", apps_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    app.add_error_handler(error_handler)

    logger.debug("Bot is polling. Press Ctrl+C to stop.")
    app.run_polling()
