from loguru import logger
from opendesk.config import OLLAMA_HOST

# Keywords that indicate simple OS-level execution (Levels 1-3)
LEVEL_3_KEYWORDS = [
    "volume", "mute", "unmute", "battery", "time", "date", 
    "brightness", "wifi", "bluetooth", "sleep", "restart", "shutdown",
    "open", "close", "launch", "kill", "type", "play", "pause", "next", "previous"
]

# Keywords that indicate medium complexity, needing search or APIs (Levels 4-7)
LEVEL_7_KEYWORDS = [
    "search", "google", "summarize", "read", "file", "folder", "create", 
    "document", "excel", "powerpoint", "write", "email", "message", "send"
]

# Keywords that indicate complex UI interactions needing Vision (Levels 8-10)
LEVEL_10_KEYWORDS = [
    "click", "see", "look", "find", "screen", "button", "icon", "image", "picture"
]

def fallback_score_command(command: str) -> int:
    """Legacy keyword-based scoring as fallback."""
    command_lower = command.lower()
    if any(keyword in command_lower for keyword in LEVEL_10_KEYWORDS):
        return 9
    if any(keyword in command_lower for keyword in LEVEL_7_KEYWORDS):
        return 6
    if any(keyword in command_lower for keyword in LEVEL_3_KEYWORDS):
        return 2
    return 5

ROUTER_PROMPT = """You are a Semantic Router for a PC assistant.
Categorize the user's command into EXACTLY ONE of these categories:
1. "SIMPLE" : Single-step OS actions (volume, mute, open app, play spotify, take screenshot, battery/status).
2. "MEDIUM" : Two-step tasks or basic data retrieval without UI vision (search, read basic file).
3. "COMPLEX" : Multi-step tasks, document editing, email, file sharing, UI searching/clicking, reading screen.

Return ONLY a strictly valid JSON object: {{"category": "<CATEGORY_NAME>", "score": <1-10>}}
Score 1-3 for SIMPLE. Score 4-7 for MEDIUM. Score 8-10 for COMPLEX.
Command: {command}
"""

async def get_routing_info(command: str) -> dict:
    """
    Returns routing instructions using gemma3:12b with a fallback to keywords.
    """
    try:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(
            model="gemma3:12b",
            base_url=OLLAMA_HOST,
            temperature=0.0,
            format="json"
        )
        resp = await llm.ainvoke(ROUTER_PROMPT.format(command=command))
        content = resp.content.upper()
        
        category = "COMPLEX"
        if "SIMPLE" in content:
            category = "SIMPLE"
        elif "MEDIUM" in content:
            category = "MEDIUM"
            
        score = 10
        import re
        s_match = re.search(r'"score"[\\]*"\s*:\s*(\d+)', resp.content, re.IGNORECASE) or re.search(r'"score"\s*:\s*(\d+)', resp.content, re.IGNORECASE)
        if s_match:
            try:
                score = int(s_match.group(1))
            except Exception as e:
                logger.debug(f"Failed to capture integer score: {e}")
                
        logger.debug(f"LLM Semantic Router classified '{command}' as {category} (Score: {score})")
        
    except Exception as e:
        import traceback
        with open("trace.txt", "w") as f:
            traceback.print_exc(file=f)
        logger.warning(f"LLM Semantic Router failed ({e}). Using keyword fallback.")
        score = fallback_score_command(command)
        if score <= 3:
            category = "SIMPLE"
        elif score <= 7:
            category = "MEDIUM"
        else:
            category = "COMPLEX"

    # Compile the routing payload
    if category == "SIMPLE" or score <= 3:
        return {
            "level": "simple",
            "score": score,
            "skip_memory": True,
            "skip_judge": True,
            "history_limit": 1
        }
    elif category == "MEDIUM" or score <= 7:
        return {
            "level": "medium",
            "score": score,
            "skip_memory": False,
            "skip_judge": True,
            "history_limit": 3
        }
    else:
        return {
            "level": "complex",
            "score": score,
            "skip_memory": False,
            "skip_judge": False,
            "history_limit": 20
        }

