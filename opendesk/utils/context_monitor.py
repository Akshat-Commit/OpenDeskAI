import threading
import time
from loguru import logger
import psutil # type: ignore
import pygetwindow as gw # type: ignore

class ContextMonitor:
    def __init__(self, interval_seconds: int = 5):
        self.interval_seconds = interval_seconds
        self.active_window_title = ""
        self.cpu_percent = 0.0
        self.memory_percent = 0.0
        self.is_running = False
        self._thread = None

    def start(self):
        """Starts the background monitoring thread."""
        if self.is_running:
            return
        
        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("ContextMonitor started in the background.")

    def stop(self):
        """Stops the background monitoring thread."""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            logger.info("ContextMonitor stopped.")

    def _monitor_loop(self):
        """Internal loop to periodically fetch system state."""
        while self.is_running:
            try:
                # Get active window
                active_window = gw.getActiveWindow()
                if active_window is not None:
                    self.active_window_title = active_window.title
                else:
                    self.active_window_title = "None (Desktop or Lock Screen)"

                # Get system resources
                self.cpu_percent = psutil.cpu_percent(interval=None) # type: ignore
                self.memory_percent = psutil.virtual_memory().percent # type: ignore

            except Exception as e:
                logger.error(f"Error in ContextMonitor loop: {e}")
                
            time.sleep(self.interval_seconds)

    def get_current_context_summary(self) -> str:
        """Returns a string summarizing the current user context."""
        summary = (
            f"Active Foreground Window: '{self.active_window_title}'\n"
            f"System CPU Usage: {self.cpu_percent}%\n"
            f"System RAM Usage: {self.memory_percent}%\n"
        )
        return summary

# Global singleton instance
monitor_instance = ContextMonitor()
