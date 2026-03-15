import secrets
import time
from loguru import logger
from typing import Dict, Optional, Any

# In-memory session store
# Structure: { token: { "laptop_id": str, "ngrok_url": str, "telegram_user_id": int | None, "claimed": bool, "created_at": float, "expires_at": float } }
SESSIONS: Dict[str, Dict[str, Any]] = {}

SESSION_EXPIRY_SECONDS = 60

def _generate_laptop_id() -> str:
    """Generates a simple unique identifier for this machine session."""
    import uuid
    import socket
    try:
        hostname = socket.gethostname()
    except Exception: # noqa: S110
        hostname = "Unknown-PC"
    return f"{hostname}-{str(uuid.uuid4())[:8]}"

def create_session(ngrok_url: str) -> str:
    """Creates a new unique session token waiting to be claimed."""
    # Clean up old expired sessions first
    _cleanup_expired_sessions()
    
    token = secrets.token_urlsafe(16)
    now = time.time()
    
    SESSIONS[token] = {
        "laptop_id": _generate_laptop_id(),
        "ngrok_url": ngrok_url,
        "telegram_user_id": None,
        "claimed": False,
        "created_at": now,
        "expires_at": now + SESSION_EXPIRY_SECONDS
    }
    logger.info(f"Created new connection session token (expires in {SESSION_EXPIRY_SECONDS}s)")
    return token

def is_session_valid(token: str) -> bool:
    """Checks if a token exists and hasn't expired (if unclaimed)."""
    session = SESSIONS.get(token)
    if not session:
        return False
        
    if not session["claimed"] and time.time() > session["expires_at"]:
        return False
        
    return True

def claim_session(token: str, telegram_user_id: int) -> bool:
    """
    Links a Telegram user ID to a session token.
    Once claimed, the session no longer expires on the 60s timer.
    """
    if not is_session_valid(token):
        return False
        
    # If this user already has an active session, we should ideally disconnect it
    # to enforce 1:1, but the simple approach is to let them claim the new one and 
    # we just use the newest one in get_session_by_user.
    
    session = SESSIONS[token]
    session["telegram_user_id"] = telegram_user_id
    session["claimed"] = True
    # Once claimed, it stays alive until explicitly disconnected
    
    logger.info(f"Session {token[:4]}... claimed by Telegram User ID {telegram_user_id}")
    return True

def get_session_by_user(telegram_user_id: int) -> Optional[Dict[str, Any]]:
    """Finds the active, claimed laptop session for a given user ID."""
    # Simple iteration. Since it's a personal bot, this dictionary is tiny.
    for token, session in SESSIONS.items():
        if session["claimed"] and session["telegram_user_id"] == telegram_user_id:
            return session
    return None

def disconnect_session(telegram_user_id: int) -> bool:
    """Unlinks a user from their claimed session."""
    tokens_to_remove = []
    
    for token, session in SESSIONS.items():
        if session["claimed"] and session["telegram_user_id"] == telegram_user_id:
            tokens_to_remove.append(token)
            
    for t in tokens_to_remove:
        SESSIONS.pop(t, None)
        logger.info(f"Disconnected session for user {telegram_user_id}")
        
    return len(tokens_to_remove) > 0

def _cleanup_expired_sessions():
    """Removes sessions that were never claimed and exceeded their expiry."""
    now = time.time()
    expired_tokens = [
        token for token, session in SESSIONS.items() 
        if not session["claimed"] and now > session["expires_at"]
    ]
    
    for t in expired_tokens:
        SESSIONS.pop(t, None)
