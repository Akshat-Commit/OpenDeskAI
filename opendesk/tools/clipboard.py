import pyperclip # type: ignore
from loguru import logger
from opendesk.tools.registry import register_tool

@register_tool("read_clipboard")
def read_clipboard(max_chars: int = 2000) -> str:
    """Reads the current text content of the computer's clipboard. Returns up to max_chars characters."""
    try:
        content = pyperclip.paste()
        
        if not content:
            return "The clipboard is currently empty."
            
        content_length = len(content)
        if content_length > max_chars:
            content = content[:max_chars] + f"\n\n...[Truncated {content_length - max_chars} characters to protect chat limits]"
            
        return f"Currently copied on clipboard:\n\n{content}"
    except Exception as e:
        logger.error(f"Error reading clipboard: {e}")
        return f"Failed to read clipboard: {e}"

@register_tool("write_clipboard")
def write_clipboard(content: str) -> str:
    """Copies text directly to the computer's clipboard, allowing the user to paste it anywhere."""
    try:
        pyperclip.copy(content)
        return f"Successfully copied {len(content)} characters to the PC clipboard. Ready to paste!"
    except Exception as e:
        logger.error(f"Error writing to clipboard: {e}")
        return f"Failed to write to clipboard: {e}"
