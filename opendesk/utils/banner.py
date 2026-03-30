from rich.console import Console, Group
from rich.text import Text
from rich.align import Align
import shutil
import sys

# Detect headless mode (running via PM2 / no interactive terminal)
IS_HEADLESS = not sys.stdout.isatty()

# Force console to use exact terminal width to prevent collapsing
console = Console(width=shutil.get_terminal_size().columns)

OPENDESK_ART = """
      ░█████╗░██████╗░███████╗███╗░░██╗██████╗░███████╗░██████╗██╗░░██╗
      ██╔══██╗██╔══██╗██╔════╝████╗░██║██╔══██╗██╔════╝██╔════╝██║░██╔╝
      ██║░░██║██████╔╝█████╗░░██╔██╗██║██║░░██║█████╗░░╚█████╗░█████═╝░
      ██║░░██║██╔═══╝░██╔══╝░░██║╚████║██║░░██║██╔══╝░░░╚═══██╗██╔═██╗░
      ╚█████╔╝██║░░░░░███████╗██║░╚███║██████╔╝███████╗██████╔╝██║░╚██╗
      ░╚════╝░╚═╝░░░░░╚══════╝╚═╝░░╚══╝╚═════╝░╚══════╝╚═════╝░╚═╝░░╚═╝
"""

def get_banner_renderable():
    """Returns the original professional UPPERCASE banner."""
    # Line-by-line centering exactly like setup_wizard.py for bit-perfect parity
    lines = [Text()] # One top spacing line
    for line in OPENDESK_ART.strip("\n").split("\n"):
        lines.append(Align.center(Text(line, style="bold grey82", no_wrap=True)))
    
    lines.extend([
        Text(),
        Align.center(Text("V1.0.0  |  FREE & OPEN SOURCE  |  GITHUB.COM/AKSHAT-COMMIT/OPENDESK", style="dim grey70")),
        Text()
    ])
    return Group(*lines)

def show_banner():
    """Show the professional UPPERCASE banner with hardcoded ASCII art."""
    if IS_HEADLESS:
        return
    console.print(get_banner_renderable())
    
    from opendesk.config import USER_MODE

    console.print(
        f"  Mode: [cyan]{USER_MODE.upper()}[/]"
    )

    if USER_MODE == "developer":
        console.print(
            "  [red]⚡ DEVELOPER MODE[/] - Full 8 model chain active"
        )
    elif USER_MODE == "local":
        console.print(
            "  [green]🏠 LOCAL MODE[/] - Ollama only"
        )
    elif USER_MODE == "cloud":
        console.print(
            "  [cyan]☁️ CLOUD MODE[/] - Groq + Ollama fallback"
        )

def get_mode_renderable(mode: str):
    """Returns the original prominently highlighted mode message."""
    # Green-ish background for all modes per user request
    bg_color = "green"
    label = f"[bold black on {bg_color}]  {mode.upper()} MODE ACTIVATED  [/bold black on {bg_color}]"
    return Group(
        Align.center(label),
        Text()
    )

def show_mode_banner(mode: str):
    """Shows a prominent full-width monochromatic mode message."""
    if IS_HEADLESS or not mode:
        return
    console.print(get_mode_renderable(mode))

def show_health_header():
    if IS_HEADLESS:
        return
    columns = shutil.get_terminal_size().columns - 1
    console.print(f"┌{'─' * (columns - 2)}┐", style="bold grey82")

def show_health_footer():
    if IS_HEADLESS:
        return
    columns = shutil.get_terminal_size().columns - 1
    console.print(f"└{'─' * (columns - 2)}┘", style="bold grey82")

def show_completion_banner():
    if IS_HEADLESS:
        return
    console.print(
        "\n      [bold green]●[/bold green] [bold grey82]OPENDESK CORE SERVICES READY[/bold grey82]"
    )
    console.print(
        "      [dim grey70]Generating secure session link...[/dim grey70]\n"
    )
