import os
from loguru import logger
from typing import Dict, List

from telegram import Update # type: ignore
from telegram.constants import ChatAction # type: ignore
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes # type: ignore

from opendesk.config import BOT_TOKEN, ALLOWED_TELEGRAM_ID # type: ignore
from opendesk.agent import run_agent_loop # type: ignore



# Maximum messages to keep in memory per chat
MAX_MEMORY = 20

# In-memory conversation history per chat
USER_HISTORY: Dict[int, List[Dict[str, str]]] = {}

# Track active agent tasks per chat for cancellation
import asyncio
ACTIVE_TASKS: Dict[int, asyncio.Task] = {}

from opendesk.db.crud import log_chat_message, get_all_screenshots, get_screenshot_by_id
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
                USER_HISTORY[chat_id] = []  # Fresh start for new session
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

async def stop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for /cancel"""
    await cancel_handler(update, context)

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any running agent task for this chat."""
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        return
        
    chat_id = update.message.chat_id
    task = ACTIVE_TASKS.get(chat_id)
    if task and not task.done():
        task.cancel()
        ACTIVE_TASKS.pop(chat_id, None)
        await update.message.reply_text("🛑 Command cancelled!")
    else:
        await update.message.reply_text("ℹ️ No active command to cancel.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming text by sending it to the local autonomous agent."""
    text = update.message.text
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    
    if not text:
        return
        
    # AUTHENTICATION CHECK
    if not is_authorized(user_id):
        # Silently ignore or send a warning once? 
        # Usually it's better to silently ignore unauthorized messages in a personal bot.
        return

    session = get_session_by_user(user_id)
        
    # AUTO-CANCEL PREVIOUS TASK
    old_task = ACTIVE_TASKS.get(chat_id)
    if old_task and not old_task.done():
        logger.info(f"Auto-cancelling previous task for chat {chat_id} due to new message.")
        old_task.cancel()

    logger.info(f"Received message from authorized user {chat_id}: {text}")
    
    # Send a processing indicator
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception as e:
        logger.warning(f"Could not send typing indicator: {e}")

    # Initialize history for this chat if not present
    if chat_id not in USER_HISTORY:
        USER_HISTORY[chat_id] = []
        
    history = USER_HISTORY[chat_id]
    
    # Log user message
    log_chat_message("user", text)
    
    try:
        import asyncio
        # Immediate feedback message
        status_msg = await update.message.reply_text("⚡ Processing...")
        
        # New direct async call to the multi-agent supervisor system
        agent_task = asyncio.create_task(run_agent_loop(text, history, 7))
        ACTIVE_TASKS[chat_id] = agent_task  # Register for /cancel
        
        # Dynamic cycling status messages
        async def update_status():
            loading_messages = [
                "🔍 Analyzing your request...",
                "🧠 Consulting Memory Agent...",
                "⚖️ Judge Agent verifying actions...",
                "⚙️ Executing tools on your laptop...",
                "📡 Communicating with AI models...",
                "🚀 Almost there, assembling response...",
                "⚡ Still processing (complex task)..."
            ]
            try:
                for msg in loading_messages:
                    await asyncio.sleep(4.0)
                    if agent_task.done():
                        break
                    try:
                        await status_msg.edit_text(msg)
                    except Exception as e:
                        logger.debug(f"Could not edit status message: {e}")
                
                while not agent_task.done():
                    await asyncio.sleep(5)
                    try:
                        await status_msg.edit_text("⏳ OpenDesk is thinking really hard...")
                    except Exception as e:
                        logger.debug(f"Could not edit status message: {e}")
                        
            except asyncio.CancelledError:
                # Proper cleanup on cancellation to avoid event loop errors
                pass
                
        updater_task = asyncio.create_task(update_status())
        
        try:
            # Wait for agent loop to complete
            result = await agent_task
            response_text, new_history, attachments = result
        except asyncio.CancelledError:
            logger.info(f"Task for chat {chat_id} was successfully cancelled.")
            # Ensure status message is deleted and re-raise to exit handler
            try:
                await status_msg.delete()
            except:
                pass
            return
        finally:
            updater_task.cancel()
            try:
                # Shield the deletion from cancellation to ensure it happens
                await asyncio.shield(status_msg.delete())
            except Exception:
                pass
            ACTIVE_TASKS.pop(chat_id, None)  # Clean up
        
        # Keep only the last MAX_MEMORY messages to prevent token bloat
        USER_HISTORY[chat_id] = new_history[-MAX_MEMORY:] 
        
        # Send text response
        if response_text and response_text.strip():
            log_chat_message("assistant", response_text)
            if len(response_text) > 4000:
                response_text = response_text[:4000] + "\n...[truncated]"
            await update.message.reply_text(response_text)
            
        # Send attachments if any tools generated files
        for file_path in attachments:
            if os.path.exists(file_path):
                ext = os.path.splitext(file_path)[1].lower() # type: ignore
                try:
                    if ext in [".png", ".jpg", ".jpeg", ".gif"]:
                        with open(file_path, "rb") as f:
                            await update.message.reply_photo(photo=f)
                    else:
                        with open(file_path, "rb") as f:
                            await update.message.reply_document(document=f)
                except Exception as e:
                    logger.error(f"Error sending attachment {file_path}: {e}")
                    await update.message.reply_text(f"Notice: Failed to upload {os.path.basename(file_path)}")
            else:
                logger.warning(f"Attachment {file_path} not found on disk.")
                
    except Exception as e:
        logger.error(f"Error in agent processing: {e}")
        from opendesk.db.crud import log_error
        import traceback
        log_error("bot.message_handler", str(e), traceback.format_exc())
        await update.message.reply_text(f"An error occurred while processing your request: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a message pointing to the logs."""
    logger.exception("Exception while handling an update:")

def run_bot():
    """Starts the long-polling Telegram bot."""
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN provided, cannot start bot.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("disconnect", disconnect_handler))
    app.add_handler(CommandHandler("cancel", cancel_handler))
    app.add_handler(CommandHandler("stop", stop_handler))
    app.add_handler(CommandHandler("screenshots", screenshots_handler))
    app.add_handler(CommandHandler("getscreenshot", getscreenshot_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    app.add_error_handler(error_handler)

    logger.info("Bot is polling. Press Ctrl+C to stop.")
    app.run_polling()
