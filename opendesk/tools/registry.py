from typing import Dict, Callable, Any
from loguru import logger



# Basic tool registry
_TOOLS: Dict[str, Callable] = {}

def register_tool(name: str):
    """Decorator to register a function as a tool."""
    def decorator(func: Callable):
        _TOOLS[name] = func
        return func
    return decorator

def execute_tool(name: str, kwargs: Dict[str, Any]) -> str:
    """Finds and executes the registered tool."""
    if name not in _TOOLS:
        error_msg = f"Tool '{name}' not found in registry."
        logger.error(error_msg)
        return error_msg
    
    try:
        func = _TOOLS[name]
        result = func(**kwargs)
        return str(result)
    except Exception as e:
        error_msg = f"Error executing tool '{name}': {e}"
        logger.error(error_msg)
        return error_msg

def get_registered_tools() -> list[str]:
    """Returns a list of all registered tool names."""
    return list(_TOOLS.keys())
