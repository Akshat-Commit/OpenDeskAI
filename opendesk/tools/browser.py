from selenium import webdriver # type: ignore
from selenium.webdriver.chrome.service import Service as ChromeService # type: ignore
from selenium.webdriver.common.by import By # type: ignore
from webdriver_manager.chrome import ChromeDriverManager # type: ignore
from .registry import register_tool



# Keep a global reference to the browser so it stays open across tool calls
_browser_instance = None

def _get_browser():
    global _browser_instance
    if _browser_instance is None:
        options = webdriver.ChromeOptions()
        # options.add_argument("--headless=new") # Make visible for desktop automation
        service = ChromeService(ChromeDriverManager().install())
        _browser_instance = webdriver.Chrome(service=service, options=options)
    return _browser_instance

@register_tool("open_url")
def open_url(url: str) -> str:
    """Opens a URL in the Chrome browser."""
    import os
    try:
        browser = _get_browser()
        
        # Handle local Windows file paths correctly
        if os.path.exists(url) and os.path.isabs(url):
            url = "file:///" + url.replace("\\", "/")
        elif url.startswith("file://"):
            # Ensure correct format for Windows: file:///C:/...
            if not url.startswith("file:///"):
                url = url.replace("file://", "file:///")
        elif not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
            
        browser.get(url)
        return f"Successfully opened {url}. Page title: {browser.title}"
    except Exception as e:
        return f"Error opening URL '{url}': {e}"

@register_tool("read_browser_text")
def read_browser_text() -> str:
    """Reads the visible text from the currently open body paragraph."""
    try:
        if _browser_instance is None:
            return "No browser is currently open. Use open_url first."
        body = _browser_instance.find_element(By.TAG_NAME, "body")
        text = body.text[:2000] # Limit to 2000 chars to avoid overwhelming LLM
        return f"Visible text (first 2000 chars):\n{text}"
    except Exception as e:
        return f"Error reading text from browser: {e}"

@register_tool("close_browser")
def close_browser() -> str:
    """Closes the current Chrome browser instance."""
    global _browser_instance
    try:
        if _browser_instance:
            _browser_instance.quit()
            _browser_instance = None
            return "Browser closed successfully."
        return "No browser instance was open."
    except Exception as e:
        return f"Error closing browser: {e}"
