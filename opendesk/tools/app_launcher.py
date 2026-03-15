import subprocess
import os
import time
import glob
from loguru import logger
from .registry import register_tool
from opendesk.db.crud import log_app_start


# Windows Start Menu shortcut locations
START_MENU_PATHS = [
    os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
]

def _find_shortcut(app_name: str) -> str:
    """Search Start Menu for a .lnk shortcut matching the app name."""
    app_lower = app_name.lower().strip()
    
    best_match = None
    best_score = 0
    
    for start_path in START_MENU_PATHS:
        if not os.path.exists(start_path):
            continue
        for lnk_file in glob.glob(os.path.join(start_path, "**", "*.lnk"), recursive=True):
            filename = os.path.splitext(os.path.basename(lnk_file))[0].lower()
            
            # Exact match
            if filename == app_lower:
                return lnk_file
            
            # Partial match scoring
            if app_lower in filename:
                score = len(app_lower) / len(filename)
                if score > best_score:
                    best_score = score
                    best_match = lnk_file
            elif filename in app_lower:
                score = len(filename) / len(app_lower) * 0.8
                if score > best_score:
                    best_score = score
                    best_match = lnk_file
    
    return best_match


@register_tool("open_app")
def open_app(app_name: str) -> str:
    """
    Opens a desktop application by name. Searches the Windows Start Menu
    shortcuts to find and launch the correct app. Works with natural names
    like 'WhatsApp', 'VS Code', 'Spotify', 'Chrome', 'Notepad', etc.
    """
    logger.info(f"Attempting to open app: {app_name}")
    app_lower = app_name.lower().strip()
    
    # Step 1: Explicit Overrides for core Windows apps that often get confused with 3rd party variants
    # For example: "notepad" vs "Notepad++"
    explicit_overrides = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
        "explorer": "explorer.exe"
    }
    
    if app_lower in explicit_overrides:
        try:
            subprocess.Popen(explicit_overrides[app_lower], shell=True, cwd=os.path.expanduser("~"))
            time.sleep(3)
            log_app_start(explicit_overrides[app_lower])
            return f"Successfully launched '{explicit_overrides[app_lower]}' via explicit override."
        except Exception as e:
            logger.warning(f"Explicit override {explicit_overrides[app_lower]} failed: {e}")
            
    # Step 2: Search the Start Menu for matching shortcut
    shortcut = _find_shortcut(app_name)
    if shortcut:
        try:
            os.startfile(shortcut)
            time.sleep(3) # Wait for app to focus
            log_app_start(app_name)
            return f"Successfully launched '{app_name}' from Start Menu."
        except Exception as e:
            logger.error(f"Failed to launch shortcut {shortcut}: {e}")
    
    # Step 2: Try common Windows URI protocols
    uri_map = {
        "whatsapp": "whatsapp:",
        "telegram": "tg:",
        "spotify": "spotify:",
        "settings": "ms-settings:",
        "store": "ms-windows-store:",
        "mail": "mailto:",
        "maps": "bingmaps:",
        "camera": "microsoft.windows.camera:",
        "calendar": "outlookcal:",
        "calculator": "calculator:",
        "clock": "ms-clock:",
        "weather": "bingweather:",
    }
    
    app_lower = app_name.lower().strip()
    for key, uri in uri_map.items():
        if key in app_lower:
            try:
                os.startfile(uri)
                time.sleep(3) # Wait for app to focus
                log_app_start(app_name)
                return f"Successfully launched '{app_name}' via Windows protocol."
            except Exception as e:
                logger.warning(f"URI protocol {uri} failed: {e}")
    
    # Step 3: Try as a direct command name
    direct_commands = {
        "notepad": "notepad",
        "calculator": "calc",
        "paint": "mspaint",
        "explorer": "explorer",
        "file explorer": "explorer",
        "cmd": "cmd",
        "powershell": "powershell",
        "task manager": "taskmgr",
        "control panel": "control",
        "snipping tool": "snippingtool",
        "word": "winword",
        "excel": "excel",
        "powerpoint": "powerpnt",
        "chrome": "chrome",
        "firefox": "firefox",
        "edge": "msedge",
        "vs code": "code",
        "vscode": "code",
        "visual studio code": "code",
    }
    
    for key, cmd in direct_commands.items():
        if key in app_lower or app_lower in key:
            try:
                subprocess.Popen(cmd, shell=True, cwd=os.path.expanduser("~"))
                time.sleep(3) # Wait for app to focus
                log_app_start(app_name)
                return f"Successfully launched '{app_name}'."
            except Exception as e:
                logger.warning(f"Direct command {cmd} failed: {e}")
    
    # Step 4: Last resort - try the raw name as a command
    try:
        subprocess.Popen(app_name, shell=True, cwd=os.path.expanduser("~"))
        time.sleep(3) # Wait for app to focus
        return f"Attempted to launch '{app_name}' directly."
    except Exception as e:
        return f"Could not find or launch '{app_name}'. Try providing the exact app name. Error: {e}"


@register_tool("close_app")
def close_app(app_name: str) -> str:
    """
    Closes a running application by name. Uses taskkill to force-close it.
    """
    logger.info(f"Attempting to close app: {app_name}")
    
    # Map common names to process names
    process_map = {
        "whatsapp": "WhatsApp.exe",
        "chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "edge": "msedge.exe",
        "notepad": "notepad.exe",
        "vs code": "Code.exe",
        "vscode": "Code.exe",
        "visual studio code": "Code.exe",
        "spotify": "Spotify.exe",
        "telegram": "Telegram.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE",
        "explorer": "explorer.exe",
        "paint": "mspaint.exe",
        "calculator": "Calculator.exe",
        "camera": "WindowsCamera.exe",
        "task manager": "Taskmgr.exe",
    }
    
    app_lower = app_name.lower().strip()
    
    # Find the process name
    process_name = None
    for key, proc in process_map.items():
        if key in app_lower or app_lower in key:
            process_name = proc
            break
    
    if not process_name:
        # Try appending .exe
        process_name = app_name.strip()
        if not process_name.lower().endswith(".exe"):
            process_name += ".exe"
    
    try:
        result = subprocess.run(
            ["taskkill", "/im", process_name, "/f"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return f"Successfully closed '{app_name}'."
        else:
            return f"Could not close '{app_name}': {result.stderr.strip()}"
    except Exception as e:
        return f"Error closing '{app_name}': {e}"
