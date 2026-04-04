"""
StartupUI — Rich Live-based animated startup display for OpenDesk.
Provides add_renderable() / update_renderable() interface used by main.py.
"""
import sys
from rich.live import Live
from rich.text import Text
from rich.console import Group

# Re-export IS_HEADLESS so main.py's import still works
IS_HEADLESS = not sys.stdout.isatty()


class StartupUI:
    """
    Wraps Rich's Live display to provide a clean progressive
    startup experience.  Supports:
        add_renderable(item)     – append a new line/block
        update_renderable(item)  – replace the LAST added item
    """

    def __init__(self):
        self._items: list = []
        self.live: Live | None = None  # injected by main.py after Live.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_renderable(self):
        """Return the current composite renderable for Rich Live."""
        return Group(*self._items) if self._items else Text("")

    def add_renderable(self, item) -> None:
        """Append a new item (Text, Align, Group…) and refresh the display."""
        self._items.append(item)
        self._refresh()

    def update_renderable(self, item) -> None:
        """Replace the last appended item and refresh the display."""
        if self._items:
            self._items[-1] = item
        else:
            self._items.append(item)
        self._refresh()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        if self.live is not None:
            try:
                self.live.update(self.get_renderable())
                self.live.refresh()
            except Exception:
                pass  # Never crash the startup sequence over a display glitch
