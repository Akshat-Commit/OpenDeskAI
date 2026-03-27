from .registry import register_tool, execute_tool, get_registered_tools

# Import tools so they register themselves upon initialization
from . import terminal
from . import filesystem
from . import system
from . import office
from . import browser
from . import app_launcher
from . import context
from . import document_reader
from . import python_execution
from . import clipboard

__all__ = [
    "register_tool", 
    "execute_tool", 
    "get_registered_tools",
    "terminal",
    "filesystem",
    "system",
    "office",
    "browser",
    "app_launcher",
    "context",
    "document_reader",
    "python_execution",
    "clipboard"
]
