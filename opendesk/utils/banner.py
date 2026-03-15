from rich.console import Console
from rich.text import Text
from rich import print as rprint
import shutil

console = Console()

OPENDESK_ART = """
░█████╗░██████╗░███████╗███╗░░██╗██████╗░███████╗░██████╗██╗░░██╗
██╔══██╗██╔══██╗██╔════╝████╗░██║██╔══██╗██╔════╝██╔════╝██║░██╔╝
██║░░██║██████╔╝█████╗░░██╔██╗██║██║░░██║█████╗░░╚█████╗░█████═╝░
██║░░██║██╔═══╝░██╔══╝░░██║╚████║██║░░██║██╔══╝░░░╚═══██╗██╔═██╗░
╚█████╔╝██║░░░░░███████╗██║░╚███║██████╔╝███████╗██████╔╝██║░╚██╗
░╚════╝░╚═╝░░░░░╚══════╝╚═╝░░╚══╝╚═════╝░╚══════╝╚═════╝░╚═╝░░╚═╝
"""

def show_banner():
    """Show the professional UPPERCASE banner with hardcoded ASCII art."""
    console.print()
    
    # Hardcoded ASCII Art
    console.print(OPENDESK_ART, style="bold white")
    
    # Version line in uppercase - Monochromatic
    console.print(
        "  V1.0.0  |  FREE & OPEN SOURCE  |  GITHUB.COM/YOURNAME/OPENDESK",
        style="dim white"
    )
    console.print()

def show_mode_banner(mode: str):
    """Shows a prominent full-width monochromatic mode message with '!' borders."""
    if not mode:
        return
    import shutil
    columns = shutil.get_terminal_size().columns
    label = f"{mode.upper()} MODE ACTIVATED"
    
    # borders using "!" and centered white text in grey
    # Using 'grey70' for the '!' borders to give that monochromatic texture
    console.print("!" * columns, style="bold grey70")
    console.print(label.center(columns), style="bold white")
    console.print("!" * columns, style="bold grey70")
    console.print()

def show_health_header():
    """Shows the generic health status header in monochromatic theme (full width)."""
    columns = shutil.get_terminal_size().columns - 1
    # Box header: ┌ + ─ * (cols - 2) + ┐
    console.print(f"┌{'─' * (columns - 2)}┐", style="bold white")

def show_health_footer():
    """Closes the generic health status box in monochromatic theme (full width)."""
    columns = shutil.get_terminal_size().columns - 1
    # Box footer: └ + ─ * (cols - 2) + ┘
    console.print(f"└{'─' * (columns - 2)}┘", style="bold white")

def show_completion_banner():
    """Shows a simple, clean, non-blocking completion message."""
    console.print(
        "\n  [bold green]●[/bold green] [bold grey70]OPENDESK READY[/bold grey70] [bold white]— SCAN QR CODE TO CONNECT[/bold white]\n"
    )

    console.print()
