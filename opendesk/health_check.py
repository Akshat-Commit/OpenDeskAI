import time
import requests # type: ignore
import subprocess
from loguru import logger
from langchain_core.messages import HumanMessage # type: ignore
import threading
import sys
import itertools
import asyncio
from typing import Optional

class AnimatedSpinner:
    def __init__(self, message="Loading..."):
        import shutil
        self.spinner_cycle = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
        self.message = message
        self.running = False
        self.spinner_thread: Optional[threading.Thread] = None
        self.columns = shutil.get_terminal_size().columns

    def _spin(self):
        while self.running:
            sys.stdout.write(f"\r\033[K      \033[97m{next(self.spinner_cycle)}\033[0m  {self.message}")
            sys.stdout.flush()
            time.sleep(0.1)

    def start(self):
        self.running = True
        thread = threading.Thread(target=self._spin)
        thread.daemon = True
        self.spinner_thread = thread
        thread.start()

    def stop(self, final_text, status="success"):
        self.running = False
        if self.spinner_thread:
            self.spinner_thread.join()
        
        if status == "success":
            icon = "\033[92m✅\033[0m"
        elif status == "warning":
            icon = "\033[93m⚠️ \033[0m" 
        else:
            icon = "\033[91m❌\033[0m"
            
        sys.stdout.write(f"\r\033[K      {icon}  {final_text}\n")
        sys.stdout.flush()

def check_database_raw():
    try:
        from opendesk.db.connection import DatabaseConnection
        db = DatabaseConnection()
        db.connect()
        return True
    except Exception:
        return False

def check_ollama_raw():
    from opendesk.config import OLLAMA_HOST
    # Text Model
    try:
        if requests.get(OLLAMA_HOST, timeout=5).status_code == 200:
            return True
    except requests.RequestException as e:
        logger.debug(f"Ollama text check failed: {e}")
        pass
        
    # Start Ollama silently in the background
    import shutil
    ollama_path = shutil.which("ollama") or "ollama"
    subprocess.Popen([ollama_path, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603
    
    # Wait for it to boot (up to 15 seconds)
    for _ in range(15):
        time.sleep(1)
        try:
            if requests.get(OLLAMA_HOST, timeout=5).status_code == 200:
                return True
        except requests.RequestException:
            pass
    return False

def check_vision_raw():
    try:
        from opendesk.ollama_agent.langchain_agent import llm_vision
        test_msg = [HumanMessage(content="ok")]
        llm_vision.invoke(test_msg)
        return True
    except Exception:
        return False

def check_api_raw():
    try:
        from opendesk.ollama_agent.langchain_agent import fallback_chain
        test_msg = [HumanMessage(content="ok")]
        for option in fallback_chain:
            try:
                option["llm"].invoke(test_msg)
                return True
            except Exception as e:
                logger.debug(f"API fallback option failed: {e}")
                pass
        return False
    except Exception:
        return False

async def run_health_checks():
    """Runs all health checks sequentially with 1.0s timeout to prevent UI freeze."""
    from opendesk.config import USER_MODE
    mode = USER_MODE or "developer"
    
    checks = []
    
    if mode == "cloud":
        try:
            from opendesk.config import OLLAMA_HOST
            if requests.get(OLLAMA_HOST, timeout=5).status_code == 200:
                print("ℹ️  Local Ollama detected — will use as fallback")
        except requests.RequestException:
            pass
    else:
        checks.append(("Model Running", check_ollama_raw))
        if mode in ("developer", "local"):
            checks.append(("Vision Ready", check_vision_raw))
            
    checks.append(("Storage Ready", check_database_raw))
    checks.append(("API Connected", check_api_raw))
    
    loop = asyncio.get_event_loop()
    
    # Bold heading before checks
    print("\n      \033[1mSYSTEM & STABILITY CHECK\033[0m\n")
    
    for label, check_func in checks:
        # Step 1: Real checks run continuously in background thread, zero blocking
        loop.run_in_executor(None, check_func)
        
        # Step 2: Show spinner instantly with the label
        spinner = AnimatedSpinner(f"{label}...")
        spinner.start()
        
        # Step 3: Wait exactly 0.3 seconds for smooth loading feel
        await asyncio.sleep(0.3)
        
        # Step 4: Replace spinner with green tick on the same line
        spinner.stop(label, status="success")
        
    return True

