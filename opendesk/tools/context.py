from loguru import logger
from .registry import register_tool
from opendesk.utils.context_monitor import monitor_instance



@register_tool("get_current_context")
def get_current_context() -> str:
    """Gets the current context of the user, including the active foreground window they are looking at, and system CPU/RAM usage. USE THIS whenever the user asks 'what am I looking at' or 'how is my system doing'."""
    try:
        return monitor_instance.get_current_context_summary()
    except Exception as e:
        logger.error(f"Error getting context: {e}")
        return f"Error getting context: {e}"
