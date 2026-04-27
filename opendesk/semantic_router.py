from loguru import logger
from opendesk.config import GROQ_API_KEY_2, OLLAMA_HOST

# Fast-Pass Keywords
COMMAND_INDICATORS = [
    "open", "close", "play", "set", "take", "screenshot", "find", "search", 
    "read", "summarize", "create", "write", "send", "share", "volume", 
    "battery", "time", "date", "mute", "unmute"
]

ROUTER_PROMPT = """You are a Semantic Router for a PC assistant.
Categorize the user's message into EXACTLY ONE of these categories:
1. "CHAT"   : General conversation, greetings, questions about how you work, or casual talk.
2. "SIMPLE" : Single-step OS actions (volume, mute, open app, play spotify, take screenshot, battery/status).
3. "MEDIUM" : Two-step tasks or basic data retrieval (search, read basic file).
4. "COMPLEX": Multi-step tasks, document editing, email, file sharing, UI clicking.

Return ONLY a strictly valid JSON object: {{"category": "<CATEGORY_NAME>", "score": <1-10>}}
Score 1-3 for SIMPLE. Score 4-7 for MEDIUM. Score 8-10 for COMPLEX. For CHAT, score 0.
Message: {command}
"""

async def get_routing_info(command: str) -> dict:
    """
    Returns routing instructions using Groq for speed.
    Detects if the message is a COMMAND or a CHAT.
    """
    command_lower = command.lower().strip()
    
    # ── FAST-PASS ──────────────────────────────────────────────────
    if "whatsapp" in command_lower or "wa " in command_lower:
        return {"level": "medium", "score": 4, "skip_judge": True, "is_chat": False}
        
    try:
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            groq_api_key=GROQ_API_KEY_2,
            temperature=0.0
        )
        resp = await llm.ainvoke(ROUTER_PROMPT.format(command=command))
        content = resp.content.upper()
        
        category = "CHAT"
        if "SIMPLE" in content: category = "SIMPLE"
        elif "MEDIUM" in content: category = "MEDIUM"
        elif "COMPLEX" in content: category = "COMPLEX"
        
        is_chat = (category == "CHAT")
        
        # Extract score
        import re
        s_match = re.search(r'"score"\s*:\s*(\d+)', resp.content, re.IGNORECASE)
        score = int(s_match.group(1)) if s_match else (0 if is_chat else 5)
                
        logger.debug(f"Router classified '{command}' as {category} (is_chat={is_chat})")
        
        return {
            "level": category.lower(),
            "score": score,
            "skip_judge": (category in ["SIMPLE", "MEDIUM", "CHAT"]),
            "is_chat": is_chat
        }
        
    except Exception as e:
        logger.warning(f"Semantic Router failed ({e}). Defaulting to command.")
        return {"level": "medium", "score": 5, "skip_judge": False, "is_chat": False}


