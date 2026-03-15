from loguru import logger
from typing import Dict, List, Tuple, Optional

from opendesk.ollama_agent.langchain_agent import run as run_langchain



async def run_agent_loop(user_text: str, history: Optional[List[Dict[str, str]]] = None, max_steps: int = 5) -> Tuple[str, List[Dict[str, str]], List[str]]:
    """
    Wrapper for the Telegram bot to use the LangChain ReAct agent.
    Maintains compatibility with bot.py's history dictionary format.
    """
    current_history = list(history) if history else []
    
    # Format history into a readable string for the LangChain agent
    memory_str = ""
    if current_history:
        for msg in current_history:
            role = msg["role"].capitalize()
            memory_str += f"{role}: {msg['content']}\n"
            
    logger.info("Invoking LangChain Agent...")
    
    # Run LangChain agent
    final_answer, attachments = await run_langchain(user_text, memory_history=memory_str)
    
    # Update local history
    current_history.append({"role": "user", "content": user_text})
    current_history.append({"role": "assistant", "content": final_answer})
    
    return final_answer, current_history, attachments
