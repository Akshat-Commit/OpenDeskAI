import asyncio
import os
from loguru import logger
from opendesk.agent import run_agent_loop  # type: ignore
from opendesk.db.crud import log_chat_message # type: ignore
from telegram.constants import ChatAction # type: ignore

from typing import Optional
from telegram import Message # type: ignore

from opendesk.core.simple_memory import simple_memory

def get_initial_status(command: str) -> str:
    cmd = command.lower()
    if any(w in cmd for w in ["summarize", "summary", "read"]):
        return "📖 Reading your request..."
    elif any(w in cmd for w in ["find", "search", "where", "locate"]):
        return "🔍 Searching..."
    elif any(w in cmd for w in ["open", "launch", "start"]):
        return "🚀 Launching..."
    elif any(w in cmd for w in ["send", "share", "whatsapp"]):
        return "📤 Preparing..."
    elif any(w in cmd for w in ["screenshot", "capture", "screen"]):
        return "📸 Capturing..."
    elif any(w in cmd for w in ["play", "music", "spotify"]):
        return "🎵 Loading music..."
    elif any(w in cmd for w in ["create", "make", "write"]):
        return "✏️ Creating..."
    elif any(w in cmd for w in ["volume", "sound", "mute"]):
        return "🔊 Adjusting..."
    else:
        return "⚡ Processing..."


class TaskManager:
    def __init__(self):
        self.processor_task: Optional[asyncio.Task] = None
        self.current_task: Optional[asyncio.Task] = None
        self.is_running = False
        self.status_message: Optional[Message] = None
        self.queue = asyncio.Queue()
        
    async def start_queue_processor(self):
        """Starts the background worker to process commands one by one."""
        logger.debug("Task queue processor started.")
        while True:
            try:
                task_data = await self.queue.get()
                
                # We wrap the execution in a task so we can cancel it specifically
                task = asyncio.create_task(self.execute_task(task_data))
                self.current_task = task
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info("Individual task was cancelled.")
                finally:
                    self.current_task = None
                    self.queue.task_done()
            except Exception as e:
                logger.error(f"Queue error: {e}")
                self.is_running = False
                self.status_message = None
    
    async def add_to_queue(self, update, context, command, status_msg=None, routing_info=None):
        """Adds a new command to the global queue."""
        queue_size = self.queue.qsize()
        
        if self.is_running and queue_size > 0:
            # If already running, notify about the queue position
            if not status_msg:
                status_msg = await update.message.reply_text(f"⏳ Added to queue ({queue_size} waiting)")
            else:
                await status_msg.edit_text(f"⏳ Added to queue ({queue_size} waiting)")
            
            await self.queue.put({
                "update": update,
                "context": context,
                "command": command,
                "status_msg": status_msg,
                "routing_info": routing_info
            })
        else:
            await self.queue.put({
                "update": update,
                "context": context,
                "command": command,
                "status_msg": status_msg,
                "routing_info": routing_info
            })
    
    async def cancel_current_task(self):
        """Cancels the currently running task if any."""
        task = self.current_task
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def execute_task(self, task_data):
        """The actual logic to run the agent with status updates and state management."""
        update = task_data["update"]
        context = task_data["context"]
        command = task_data["command"]
        status_msg = task_data.get("status_msg")
        routing_info = task_data.get("routing_info")
        chat_id = update.message.chat_id
        
        # Add current user command to memory
        simple_memory.add(chat_id, "user", command)
        
        # Retrieve context to pass to agent
        history = simple_memory.get_context(chat_id)

        # Mark as running
        self.is_running = True
        
        log_chat_message("user", command)
        
        initial_status = get_initial_status(command)
        if status_msg:
            self.status_message = status_msg
            try:
                await self.status_message.edit_text(initial_status)
            except Exception as e:
                logger.debug(f"Failed to edit status message: {e}")
        else:
            self.status_message = await update.message.reply_text(initial_status)
        
        async def status_callback(status: str):
            """Update the status message in real-time."""
            msg = self.status_message
            if msg:
                try:
                    await msg.edit_text(status)
                except Exception as e:
                    logger.debug(f"Status update failed: {e}")

        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            
            # Pass chat_id to tools so request_confirmation can register pending actions
            from opendesk.tools.system import set_tool_chat_id
            set_tool_chat_id(chat_id)
            
            # Execute actual agent loop
            response_text, _, attachments = await run_agent_loop(
                command, history, status_callback=status_callback, routing_info=routing_info
            )
            # Update History with agent's final answer
            if response_text and response_text.strip():
                simple_memory.add(chat_id, "assistant", response_text)
            
            # ATTACHMENT MEMORY: Store file paths in memory so the agent knows
            # what files were created this turn and can reference them in follow-ups.
            # e.g. user: "send me that screenshot" -> agent finds the path here.
            if attachments:
                paths_note = "[FILES CREATED THIS TURN]: " + " | ".join(
                    f"{os.path.basename(p)} (path: {p})" for p in attachments
                )
                simple_memory.add(chat_id, "system", paths_note)

            # SEND ATTACHMENTS
            # Before editing status message
            if attachments:
                for file_path in attachments:
                    file_path_str = str(file_path)
                    if os.path.exists(file_path_str):
                        try:
                            # Detect file type
                            ext = os.path.splitext(file_path_str)[1].lower()
                            
                            # Send as photo if image
                            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                                with open(file_path_str, 'rb') as f:
                                    await context.bot.send_photo(
                                        chat_id=chat_id,
                                        photo=f,
                                        caption=f"📎 {os.path.basename(file_path_str)}"
                                    )
                            # Send as document for all other files
                            else:
                                with open(file_path_str, 'rb') as f:
                                    await context.bot.send_document(
                                        chat_id=chat_id,
                                        document=f,
                                        filename=os.path.basename(file_path_str),
                                        caption=f"📎 {os.path.basename(file_path_str)}",
                                        read_timeout=60, write_timeout=60
                                    )
                                
                            logger.info(f"File attachment processed: {file_path_str}")
                        except Exception as e:
                            logger.error(f"Failed to send file: {e}")
                            await update.message.reply_text(f"❌ Found file but could not send it: {e}")
                    else:
                        logger.warning(f"Attachment not found: {file_path_str}")

            # Send text response
            if response_text and response_text.strip():
                log_chat_message("assistant", response_text)
                
                if len(response_text) > 4000:
                    response_text = response_text[:4000] + "\n...[truncated]"
                try:
                    await update.message.reply_text(response_text, read_timeout=30, write_timeout=30, parse_mode="Markdown")
                except Exception as e:
                    # Fallback without Markdown if parsing fails
                    try:
                        await update.message.reply_text(response_text, read_timeout=30, write_timeout=30)
                    except Exception as e_inner:
                        logger.error(f"Telegram network timeout while sending final reply: {e_inner}")
                
            # THEN update status message
            msg = self.status_message
            if msg:
                try:
                    await msg.edit_text("✅ Done!")
                    # Auto-delete after a brief moment to keep chat clean
                    await asyncio.sleep(1)
                    await msg.delete()
                except Exception as e:
                    logger.debug(f"Status message delete error: {e}")
                finally:
                    self.status_message = None

        except asyncio.CancelledError:
            msg = self.status_message
            if msg:
                try:
                    await msg.edit_text("🛑 Cancelled!")
                    await asyncio.sleep(2)
                    await msg.delete()
                except Exception as e:
                    logger.debug(f"Failed to clear cancelled message: {e}")
            raise
        except Exception as e:
            logger.error(f"Task error: {e}")
            msg = self.status_message
            if msg:
                try:
                    await msg.edit_text(f"❌ Failed: {e}")
                except Exception as exc:
                    logger.debug(f"Failed to set error status: {exc}")
        finally:
            # CRITICAL: Always reset these
            self.is_running = False
            self.status_message = None
            logger.info(f"Task for chat {chat_id} completed.")

# Single global instance
task_manager = TaskManager()
