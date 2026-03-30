import pyautogui
from PIL import ImageGrab
import os
import subprocess
import time
from datetime import datetime
from .registry import register_tool
from loguru import logger
from opendesk.db.crud import log_screenshot



from opendesk.utils.ocr_analyzer import ocr_analyzer

@register_tool("take_screenshot")
def take_screenshot(context: str = "manual screenshot", save_path: str = None) -> str:
    """Takes a screenshot of the primary screen, saves it, and runs OCR in the background."""
    try:
        from datetime import datetime
        
        if not save_path:
            # 1. Prepare directory
            shot_dir = os.path.join("data", "screenshots")
            os.makedirs(shot_dir, exist_ok=True)
            
            # 2. Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(shot_dir, f"screenshot_{timestamp}.png")
        else:
            # Create parent dirs safely if save_path has a directory
            if os.path.dirname(save_path):
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
        # 3. Capture and save
        screenshot = ImageGrab.grab()
        screenshot.save(save_path)
        
        # 4. Trigger OCR in background (Zero impact on response time)
        ocr_analyzer.analyze_in_background(save_path)
        
        # 5. Record in database (legacy)
        log_screenshot(save_path, context)
        
        return f"Screenshot saved successfully at {os.path.abspath(save_path)} and queued for OCR."
    except Exception as e:
        return f"Error taking screenshot: {e}"

@register_tool("type_text")
def type_text(text: str, press_enter: bool = False) -> str:
    """Types text on the keyboard using GUI automation."""
    try:
        pyautogui.write(text, interval=0.01)
        if press_enter:
            pyautogui.press('enter')
        return f"Typed injected text: '{text}'"
    except Exception as e:
        return f"Error typing text: {e}"

@register_tool("press_key")
def press_key(key: str) -> str:
    """Presses a specific keyboard key (e.g. 'enter', 'win', 'space')."""
    try:
        pyautogui.press(key)
        return f"Pressed key '{key}'"
    except Exception as e:
        return f"Error pressing key '{key}': {e}"

@register_tool("click_mouse")
def click_mouse(x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> str:
    """Clicks the mouse at current location or specified x,y coordinates."""
    try:
        if x is not None and y is not None:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            return f"Clicked {button} button {clicks} time(s) at ({x}, {y})"
        else:
            pyautogui.click(button=button, clicks=clicks)
            return f"Clicked {button} button {clicks} time(s) at current position"
    except Exception as e:
        return f"Error clicking mouse: {e}"

@register_tool("capture_webcam")
def capture_webcam(save_path: str = None) -> str:
    """Takes a photo using the computer's webcam and saves it."""
    import cv2
    import time
    cap = None
    try:
        if not save_path:
            shot_dir = os.path.join("data", "screenshots")
            os.makedirs(shot_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(shot_dir, f"webcam_{timestamp}.jpg")
        
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return "Error: Could not open the webcam."
        
        # Read a few frames to let the camera adjust to light
        for _ in range(10):
            cap.read()
            time.sleep(0.05)
            
        ret, frame = cap.read()
        
        if ret and frame is not None and frame.size > 0:
            cv2.imwrite(save_path, frame)
            log_screenshot(save_path, "webcam capture")
            return f"Webcam photo saved successfully at {os.path.abspath(save_path)}"
        else:
            return "Error: Could not capture a valid frame from the webcam."
    except Exception as e:
        return f"Error using webcam: {e}"
    finally:
        if cap is not None:
            cap.release()

@register_tool("open_camera_app")
def open_camera_app() -> str:
    """Opens the Windows Camera application on the host screen for the user."""
    import subprocess
    try:
        subprocess.run(["cmd", "/c", "start", "microsoft.windows.camera:"])  # noqa: S607
        return "Successfully opened the Windows Camera app on the screen."
    except Exception as e:
        return f"Error opening camera app: {e}"

@register_tool("capture_video")
def capture_video(duration: int = 5, save_path: str = None) -> str:
    """Records a video using the computer's webcam for the specified duration (in seconds) and saves it."""
    import cv2
    import time
    from datetime import datetime
    import os
    
    cap = None
    out = None
    try:
        if not save_path:
            shot_dir = os.path.join("data", "screenshots")
            os.makedirs(shot_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(shot_dir, f"webcam_video_{timestamp}.mp4")
            
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return "Error: Could not open the webcam for video."
        
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0.0 or fps < 10:
            fps = 20.0 

        fourcc = cv2.VideoWriter_fourcc(*'mp4v') # type: ignore
        out = cv2.VideoWriter(save_path, fourcc, fps, (frame_width, frame_height))
        
        if not out.isOpened():
             return "Error: Could not initialize video writer."

        start_time = time.time()
        frames_captured = 0
        while int(time.time() - start_time) < duration:
            ret, frame = cap.read()
            if ret:
                out.write(frame)
                frames_captured += 1
            else:
                break
                
        if out is not None:
            out.release()
            out = None
            
        if frames_captured > 0:
            return f"Webcam video saved successfully at {os.path.abspath(save_path)}"
        else:
            return "Error: Could not capture any video frames."
    except Exception as e:
        return f"Error recording video: {e}"
    finally:
        if out is not None:
            out.release()
        if cap is not None:
            cap.release()

@register_tool("send_whatsapp_message")
def send_whatsapp_message(
    contact_name: str,
    message: str = ""
) -> str:
    """
    Opens WhatsApp Desktop and sends
    a text message to a contact.
    Use ONLY for text messages.
    NOT for file sharing.
    """
    import subprocess
    import time
    import pyautogui
    import pyperclip
    
    try:
        # Open WhatsApp
        subprocess.Popen(["whatsapp:"], shell=True)  # noqa: S602, S607
        time.sleep(3)
        
        # Search for contact
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(1)
        pyautogui.typewrite(
            contact_name,
            interval=0.05
        )
        time.sleep(2)
        pyautogui.press('enter')
        time.sleep(1)
        
        # Type and send message
        if message:
            pyperclip.copy(message)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
        
        return (
            f"Message sent to "
            f"{contact_name} on WhatsApp"
        )
    except Exception as e:
        return f"WhatsApp error: {e}"

@register_tool("send_whatsapp_file")
def send_whatsapp_file(
    contact_name: str,
    filename: str
) -> str:
    """
    Finds a file and sends it to a
    contact on WhatsApp Desktop.
    Use when user says:
    send [file] to [person] on whatsapp
    share [file] with [person] on whatsapp
    """
    import subprocess
    import time
    import pyautogui
    import pyperclip
    from opendesk.utils.file_indexer import (
        file_indexer
    )
    
    try:
        # Step 1: Find the file
        results = file_indexer.find_file(
            filename
        )
        
        if not results:
            return (
                f"Could not find {filename}. "
                f"Please check the filename."
            )
        
        file_path = results[0][0]
        
        # Step 2: Open WhatsApp
        subprocess.Popen(["whatsapp:"], shell=True)  # noqa: S602, S607
        time.sleep(3)
        
        # Step 3: Search contact
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(1)
        pyautogui.typewrite(
            contact_name,
            interval=0.05
        )
        time.sleep(2)
        pyautogui.press('enter')
        time.sleep(1)
        
        # Step 4: Attach file
        # Click attachment button
        pyautogui.hotkey('ctrl', 'shift', 'a')
        time.sleep(1)
        
        # Type file path in dialog
        pyperclip.copy(file_path)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(1)
        
        # Step 5: Send
        pyautogui.press('enter')
        time.sleep(1)
        
        return (
            f"File {filename} sent to "
            f"{contact_name} on WhatsApp! ✅"
        )
        
    except Exception as e:
        return f"WhatsApp file send error: {e}"

@register_tool("play_spotify_music")
def play_spotify_music(song_name: str) -> str:
    """A highly reliable macro that opens Spotify desktop, searches for the exact song, and plays the top result."""
    try:
        # 1. Open Spotify via Windows URI
        subprocess.run(["cmd", "/c", "start", "spotify:"])  # noqa: S607
        # Give Spotify plenty of time to launch and focus
        time.sleep(5)
        
        # Maximize the window to ensure predictable layout for coordinate fallback
        pyautogui.hotkey('win', 'up')
        time.sleep(1)
        
        # 2. Focus and CLEAR the search bar (Ctrl+L in Spotify)
        pyautogui.hotkey('ctrl', 'l')
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        time.sleep(0.5)
        
        # 3. Type song name and submit search
        logger.info(f"Typing song name: {song_name}")
        pyautogui.write(song_name, interval=0.05)
        time.sleep(1) 
        pyautogui.press('enter')
        time.sleep(4) # Increased wait for search results to load
        
        # 4. Method A: Tab sequence to "Top Result" play button
        # Usually from search box: Tab -> Clear [x] -> Top/Songs filter -> Top Result Card -> Play Button
        # We try a few tabs followed by space/enter to hit the play button
        logger.info("Trying Method A (Tab sequence)...")
        for _ in range(5):
            pyautogui.press('tab')
            time.sleep(0.2)
        pyautogui.press('enter')
        time.sleep(2)
        
        # 5. Method B (Fallback): Double click the center of the "Top Result" card
        # On a maximized window, the Top Result card is at roughly x=25%, y=45%
        logger.info("Trying Method B (Coordinate click fallback)...")
        screen_w, screen_h = pyautogui.size()
        click_x = int(screen_w * 0.25)
        click_y = int(screen_h * 0.45)
        
        pyautogui.moveTo(click_x, click_y)
        pyautogui.doubleClick()
        time.sleep(2)
        
        # 6. Method C: The 'k' shortcut (Spotify play/pause toggle)
        # Sometimes focus is on the card but play didn't trigger. 
        # 'k' is a common media key for several apps including Spotify.
        pyautogui.press('k')
        time.sleep(1)
        
        # Final press enter as many Spotify versions play on enter when card is focused
        pyautogui.press('enter')
        
        return f"Successfully executed Spotify macro: Played '{song_name}'."
    except Exception as e:
        logger.error(f"Spotify macro failed: {e}")
        return f"Error executing Spotify macro: {e}"

@register_tool("control_media")
def control_media(action: str) -> str:
    """Controls system media playback using native Windows media keys."""
    valid_actions = {
        "playpause": "playpause",
        "next": "nexttrack",
        "previous": "prevtrack",
        "mute": "volumemute"
    }
    
    action = action.lower().strip()
    if action not in valid_actions:
        return f"Error: Invalid action '{action}'. Valid actions are: {', '.join(valid_actions.keys())}."
        
    try:
        pyautogui.press(valid_actions[action])
        return f"Successfully executed media control: {action}"
    except Exception as e:
        logger.error(f"Media control failed: {e}")
        return f"Error executing media control: {e}"

@register_tool("set_volume")
def set_volume(level: int) -> str:
    """Sets the system master volume to an exact percentage (0-100)."""
    try:
        from pycaw.pycaw import AudioUtilities
        import pythoncom
        
        # Initialize COM for this thread
        pythoncom.CoInitialize()
        
        try:
            if not 0 <= level <= 100:
                return f"Error: Volume level {level} is out of bounds. Must be between 0 and 100."
                
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            
            # Calculate scalar volume (0.0 to 1.0)
            scalar_vol = float(level) / 100.0
            
            # Unmute if muted
            if volume.GetMute():
                volume.SetMute(0, None)
                
            volume.SetMasterVolumeLevelScalar(scalar_vol, None)
            
            return f"Successfully set system volume to {level}%."
        finally:
            # Always uninitialize COM
            pythoncom.CoUninitialize()
            
    except ImportError:
        return "Error: pycaw or comtypes library is missing. The user must run `pip install pycaw comtypes` to enable exact volume control."
    except Exception as e:
        logger.error(f"Failed to set volume via pycaw: {e}")
        return f"Error setting volume: {e}"



@register_tool("get_running_processes")
def get_running_processes(name_filter: str = "") -> str:
    """Returns a list of running processes, optionally filtered by name."""
    import psutil
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                info = proc.info
                # Add if no filter, or if filter matches (case-insensitive)
                if not name_filter or name_filter.lower() in str(info['name']).lower():
                    # Keep memory info clean (in MB)
                    mem_mb = info['memory_info'].rss / (1024 * 1024) if info['memory_info'] else 0
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'],
                        'memory_mb': round(mem_mb, 1)
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        if not processes:
            return f"No processes found matching '{name_filter}'." if name_filter else "No accessible processes found."
            
        # Sort by memory usage descending
        processes.sort(key=lambda x: x['memory_mb'], reverse=True)
        
        # Limit to top 20 to avoid blowing up the LLM context limit
        result_str = f"Top {min(20, len(processes))} Running Processes:\n"
        result_str += f"{'PID':<8} | {'Name':<30} | {'Memory (MB)':<10}\n"
        result_str += "-" * 55 + "\n"
        
        for p in processes[:20]:
            pid_val = p.get('pid', '')
            name_val = str(p.get('name', ''))[:30]
            mem_val = p.get('memory_mb', 0)
            result_str += f"{pid_val:<8} | {name_val:<30} | {mem_val:<10}\n"
            
        return result_str
    except Exception as e:
        logger.error(f"Failed to get running processes: {e}")
        return f"Error getting processes: {e}"

@register_tool("terminate_process")
def terminate_process(pid: int) -> str:
    """Gracefully terminates a running process by its exact PID."""
    import psutil
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()
        # Wait up to 3 seconds for it to die
        proc.wait(timeout=3)
        return f"Successfully terminated process '{name}' (PID: {pid})."
    except psutil.NoSuchProcess:
        return f"Error: No process found with PID {pid}."
    except psutil.AccessDenied:
        return f"Error: Access denied to terminate PID {pid}. You may need Administrator privileges."
    except psutil.TimeoutExpired:
        # If graceful termination fails, force kill it
        try:
            proc.kill()
            return f"Forced killed process '{name}' (PID: {pid}) after graceful termination timed out."
        except Exception as kill_err:
             return f"Failed to force kill process {pid}: {kill_err}"
    except Exception as e:
        logger.error(f"Failed to terminate process {pid}: {e}")
        return f"Error terminating process: {e}"

@register_tool("use_calculator")
def use_calculator(calculation: str) -> str:
    """A reliable macro to type a calculation into the focusable window (like calculator), press enter, and take a screenshot of the result."""
    import time
    from opendesk.tools.system import take_screenshot
    
    try:
        # Type the calculation
        pyautogui.write(calculation, interval=0.05)
        pyautogui.press('enter')
        
        # Wait for result to appear
        time.sleep(0.5)
        
        # NOW take screenshot, Result will be visible!
        shot_res = take_screenshot("calculator result")
        
        return f"Successfully typed calculation '{calculation}'. Result should be visible on screen. {shot_res}"
    except Exception as e:
        logger.error(f"Calculator macro failed: {e}")
        return f"Error executing calculator macro: {e}"

@register_tool("get_current_time")
def get_current_time() -> str:
    """Returns the current system time in a readable format."""
    now = datetime.now()
    return f"The current system time is {now.strftime('%I:%M %p')}."

@register_tool("get_battery_level")
def get_battery_level() -> str:
    """Returns the current battery percentage and charging status."""
    import psutil
    battery = psutil.sensors_battery()
    if not battery:
        return "Battery information not available on this device."
    
    status = "Charging" if battery.power_plugged else "Discharging"
    return f"Battery is at {battery.percent}% ({status})."

@register_tool("get_system_info")
def get_system_info() -> str:
    """Returns basic system information (CPU usage, RAM usage, and OS)."""
    import psutil
    import platform
    
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    os_name = platform.system()
    os_release = platform.release()
    
    return f"OS: {os_name} {os_release} | CPU: {cpu}% | RAM: {ram}%"

@register_tool("search_screenshots")
def search_screenshots(query: str) -> str:
    """
    Search through all screenshots by their
    content. Finds screenshots containing
    specific text, errors, or keywords.
    Use when user asks to find a screenshot
    by what was visible on screen.
    """
    from opendesk.utils.ocr_analyzer import ocr_analyzer
    
    results = ocr_analyzer.search_screenshots(query)
    
    if not results:
        return f"No screenshots found containing '{query}'"
    
    response = f"Found {len(results)} screenshot(s) containing '{query}':\n\n"
    
    for i, result in enumerate(results, 1):
        path = result[0]
        captured = result[2]
        filename = os.path.basename(path)
        
        response += (
            f"{i}. {filename}\n"
            f"   Captured: {captured}\n"
            f"   Path: {path}\n\n"
        )
    
    return response

# Thread-local storage to pass chat_id from bot to tools
import threading
_tool_context = threading.local()

def set_tool_chat_id(chat_id: int):
    """Called by the bot before invoking the agent to pass the current chat_id to tools."""
    _tool_context.chat_id = chat_id

@register_tool("request_confirmation")
def request_confirmation(action_description: str, original_command: str) -> str:
    """
    SAFETY GATE: Call this BEFORE using WhatsApp, Gmail, or any app to share/send anything.
    Sends a YES/NO confirmation to the user on Telegram and pauses execution.
    
    Args:
        action_description: Human-readable description of what you are about to do.
                           E.g. "Send jai.pdf to Rahul on WhatsApp"
        original_command: The original user command to re-execute if confirmed.
    
    Returns "AWAITING_CONFIRMATION" — you MUST stop after calling this tool and wait.
    """
    chat_id = getattr(_tool_context, "chat_id", None)
    if chat_id is None:
        return "CONFIRMATION_SKIPPED: No chat context available. Proceed with caution."
    
    try:
        from opendesk.bot import set_pending_action
        set_pending_action(chat_id, action_description, original_command)
        logger.info(f"Confirmation requested for chat {chat_id}: {action_description}")
        return (
            f"AWAITING_CONFIRMATION: I asked the user for confirmation.\n"
            f"Action: {action_description}\n"
            f"STOP HERE. Do not proceed until user replies YES."
        )
    except Exception as e:
        logger.error(f"Failed to set pending action: {e}")
        return f"CONFIRMATION_FAILED: {e}. Use caution before proceeding."


