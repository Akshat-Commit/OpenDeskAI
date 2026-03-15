from .connection import db
from loguru import logger
from typing import List, Dict, Optional



# --- Command History ---
def log_command(command_text: str, status: str = 'pending', output: Optional[str] = None) -> int:
    try:
        cursor = db.get_cursor()
        cursor.execute(
            "INSERT INTO command_history (command_text, status, output) VALUES (?, ?, ?)",
            (command_text, status, output)
        )
        db.commit()
        return cursor.lastrowid or 0
    except Exception as e:
        logger.error(f"Failed to log command: {e}")
        return 0

def update_command_status(command_id: int, status: str, output: Optional[str] = None):
    try:
        cursor = db.get_cursor()
        cursor.execute(
            "UPDATE command_history SET status = ?, output = ? WHERE id = ?",
            (status, output, command_id)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to update command status: {e}")

# --- File Registry ---
def register_file(file_path: str, file_type: Optional[str] = None, file_hash: Optional[str] = None):
    try:
        cursor = db.get_cursor()
        cursor.execute(
            """INSERT INTO file_registry (file_path, file_type, file_hash) 
               VALUES (?, ?, ?) 
               ON CONFLICT(file_path) DO UPDATE SET 
               last_accessed = CURRENT_TIMESTAMP, 
               file_hash = excluded.file_hash""",
            (file_path, file_type, file_hash)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to register file: {e}")

# --- App Usage ---
def log_app_start(app_name: str) -> int:
    try:
        cursor = db.get_cursor()
        cursor.execute("INSERT INTO app_usage (app_name) VALUES (?)", (app_name,))
        db.commit()
        return cursor.lastrowid or 0
    except Exception as e:
        logger.error(f"Failed to log app start: {e}")
        return 0

def log_app_end(usage_id: int):
    try:
        cursor = db.get_cursor()
        cursor.execute(
            """UPDATE app_usage 
               SET end_time = CURRENT_TIMESTAMP, 
                   duration = CAST((julianday(CURRENT_TIMESTAMP) - julianday(start_time)) * 86400 AS INT) 
               WHERE id = ?""",
            (usage_id,)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log app end: {e}")

# --- User Settings ---
def set_setting(key: str, value: str):
    try:
        cursor = db.get_cursor()
        cursor.execute(
            "INSERT INTO user_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to set setting: {e}")

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        cursor = db.get_cursor()
        cursor.execute("SELECT value FROM user_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default
    except Exception as e:
        logger.error(f"Failed to get setting: {e}")
        return default

# --- Error Logs ---
def log_error(component: str, error_message: str, traceback_str: Optional[str] = None):
    try:
        cursor = db.get_cursor()
        cursor.execute(
            "INSERT INTO error_logs (component, error_message, traceback) VALUES (?, ?, ?)",
            (component, error_message, traceback_str)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log error: {e}")

# --- Chat History ---
def log_chat_message(role: str, content: str):
    try:
        cursor = db.get_cursor()
        cursor.execute(
            "INSERT INTO chat_history (role, content) VALUES (?, ?)",
            (role, content)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log chat: {e}")

def get_recent_chat_history(limit: int = 10) -> List[Dict[str, str]]:
    try:
        cursor = db.get_cursor()
        cursor.execute(
            "SELECT role, content FROM chat_history ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        # Return in ascending order (oldest to newest)
        return [{'role': row['role'], 'content': row['content']} for row in reversed(rows)]
    except Exception as e:
        logger.error(f"Failed to get chat history: {e}")
        return []
# --- Screenshots ---
def log_screenshot(file_path: str, context_description: Optional[str] = None) -> int:
    try:
        cursor = db.get_cursor()
        cursor.execute(
            "INSERT INTO screenshots (file_path, context_description) VALUES (?, ?)",
            (file_path, context_description)
        )
        db.commit()
        return cursor.lastrowid or 0
    except Exception as e:
        logger.error(f"Failed to log screenshot: {e}")
        return 0

def get_all_screenshots() -> List[Dict]:
    try:
        cursor = db.get_cursor()
        cursor.execute("SELECT id, file_path, timestamp, context_description FROM screenshots ORDER BY timestamp DESC")
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to get screenshots: {e}")
        return []

def get_screenshot_by_id(screenshot_id: int) -> Optional[Dict]:
    try:
        cursor = db.get_cursor()
        cursor.execute("SELECT id, file_path, timestamp, context_description FROM screenshots WHERE id = ?", (screenshot_id,))
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Failed to get screenshot: {e}")
        return None
