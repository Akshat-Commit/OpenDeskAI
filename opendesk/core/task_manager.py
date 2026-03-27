import asyncio
import os
from loguru import logger
from opendesk.agent import run_agent_loop # type: ignore
from opendesk.db.crud import log_chat_message # type: ignore
from telegram.constants import ChatAction # type: ignore

from typing import Optional
from telegram import Message # type: ignore

from opendesk.core.simple_memory import simple_memory

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
    
    async def add_to_queue(self, update, context, command):
        """Adds a new command to the global queue."""
        queue_size = self.queue.qsize()
        
        if self.is_running:
            # Tell user command is queued
            await update.message.reply_text(
                f"⏳ Added to queue ({queue_size + 1} waiting)"
            )
        
        await self.queue.put({
            "update": update,
            "context": context,
            "command": command
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
        chat_id = update.message.chat_id
        
        # Add current user command to memory
        simple_memory.add(chat_id, "user", command)
        
        # Retrieve context to pass to agent
        history = simple_memory.get_context(chat_id)

        # Mark as running
        self.is_running = True
        
        log_chat_message("user", command)
        
        # Send status message
        self.status_message = await update.message.reply_text("⏳ Working on it...")
        
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
            response_text, new_history, attachments = await run_agent_loop(
                command, history, status_callback=status_callback
            )
            # Update History with agent's final answer
            if response_text and response_text.strip():
                simple_memory.add(chat_id, "assistant", response_text)
            
            # AUTO-SEND: If a whatsapp_share pending action was set (by the tool),
            # immediately send the search screenshot to the user on Telegram.
            from opendesk.bot import PENDING_ACTIONS
            pending = PENDING_ACTIONS.get(chat_id)
            if pending and pending.get("type") == "whatsapp_share":
                screenshot_path = pending.get("screenshot_path")
                found = pending.get("found_contacts", [])
                file_name = pending.get("file_name", "file")
                contact_name = pending.get("contact_name", "unknown")

                if screenshot_path and os.path.exists(screenshot_path):
                    try:
                        with open(screenshot_path, "rb") as f:
                            if found:
                                options = "\n".join(f"{i+1}. {c}" for i, c in enumerate(found))
                                caption = (
                                    f"📱 **WhatsApp search results for '{contact_name}'**\n\n"
                                    f"Found contacts:\n{options}\n\n"
                                    f"Reply with **number** or **name** to send `{file_name}`, "
                                    f"or **NO** to cancel."
                                )
                            else:
                                caption = (
                                    f"📱 **WhatsApp search results for '{contact_name}'**\n\n"
                                    f"Please look at the screenshot above and reply with the "
                                    f"**exact contact name** to send `{file_name}` to, or **NO** to cancel."
                                )
                            await context.bot.send_photo(
                                chat_id=chat_id,
                                photo=f,
                                caption=caption,
                                parse_mode="Markdown"
                            )
                    except Exception as e:
                        logger.error(f"Failed to send WhatsApp screenshot: {e}")
                        await update.message.reply_text(
                            f"📱 I searched WhatsApp for '{contact_name}'. "
                            f"Reply with the contact name to confirm sending `{file_name}`, or NO to cancel."
                        )

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
                                        caption=f"📎 {os.path.basename(file_path_str)}"
                                    )
                            logger.info(f"File sent: {file_path_str}")
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
                await update.message.reply_text(response_text)
                
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
