import sys
import shutil
from typing import List
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.live import Live

# Global console instance
console = Console()

# Detect headless mode (running via PM2 / no interactive terminal)
IS_HEADLESS = not sys.stdout.isatty()

class StartupUI:
    """A pure renderable buffer that wraps unmodified output inside a centered box."""
    def __init__(self):
        self.buffer: List[RenderableType] = []
        self.live: Live = None
        
    def add_renderable(self, renderable: RenderableType):
        """Appends any rich renderable (Text, Panel, Align, etc.) to the buffer."""
        self.buffer.append(renderable)
        self.refresh()
        
    def update_renderable(self, renderable: RenderableType):
        """Replaces the last item in the buffer (mimics \\r)."""
        if self.buffer:
            self.buffer[-1] = renderable
            self.refresh()

    def refresh(self):
        if self.live:
            self.live.update(self.get_renderable(), refresh=True)

    def get_renderable(self):
        # Use shutil to get terminal size, but ensure a stable fixed width for the Panel
        cols, _ = shutil.get_terminal_size()
        # Responsive width exactly as in setup_wizard.py (min 70 for banner safety)
        width = max(70, min(cols - 4, 120))
        
        # We simply wrap the buffer in a Group and then a Panel
        return Panel(
            Group(*self.buffer),
            title="[bold grey82] ◈  OPENDESK CORE STARTUP  ◈ [/bold grey82]",
            width=width,
            padding=(1, 2),
            border_style="grey82"
        )
