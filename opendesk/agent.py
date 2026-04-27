from loguru import logger
from typing import Dict, List, Tuple, Optional, Callable

from opendesk.ollama_agent.langchain_agent import run as run_langchain
from opendesk.semantic_router import get_routing_info


async def run_agent_loop(
    user_text: str,
    history: Optional[List[Dict[str, str]]] = None,
    status_callback: Optional[Callable] = None,
    routing_info: Optional[Dict] = None,
) -> Tuple[str, List[Dict[str, str]], List[str]]:
    """
    Wrapper for the Telegram bot to use the LangChain ReAct agent.
    Accepts pre-computed routing_info from bot.py to avoid a redundant LLM call.
    """
    # 1. ANALYZE COMMAND COMPLEXITY — skip if already done by bot.py
    if routing_info is None:
        routing_info = await get_routing_info(user_text)
    
    routing = routing_info
    logger.info(f"Routing Decision: {routing['level'].upper()} (Score: {routing.get('score', '?')})")

    if status_callback:
        await status_callback(f"🧠 Working on it...")

    # 2. SMART CONTEXT WINDOW
    original_history = list(history) if history else []
    history_limit = routing.get("history_limit", 20)
    current_history = original_history[-history_limit:] if history_limit > 0 else []
    
    memory_str = ""
    if current_history:
        for msg in current_history:
            role = msg["role"].capitalize()
            memory_str += f"{role}: {msg['content']}\n"
            
    logger.info(f"Invoking LangChain Agent (History size: {len(current_history)})...")
    
    # 3. RUN AGENT
    final_answer, attachments = await run_langchain(
        user_text, 
        memory_history=memory_str,
        status_callback=status_callback,
        routing_info=routing
    )
    
    full_history = list(original_history)
    full_history.append({"role": "user", "content": user_text})
    full_history.append({"role": "assistant", "content": final_answer})
    
    return final_answer, full_history, attachments
