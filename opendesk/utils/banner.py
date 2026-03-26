from rich.console import Console
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
        "  V1.0.0  |  FREE & OPEN SOURCE  |  GITHUB.COM/AKSHAT-COMMIT/OPENDESK",
        style="dim white"
    )
    console.print()

def show_mode_banner(mode: str):
    """Shows a prominent full-width monochromatic mode message."""
    if not mode:
        return
    from rich.panel import Panel
    from rich.align import Align
    
    label = f"[bold white]{mode.upper()} MODE ACTIVATED[/bold white]"
    console.print(
        Panel(
            Align.center(label),
            border_style="bold grey70",
            expand=True
        )
    )
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
        "\n  [bold green]●[/bold green] [bold white]OPENDESK CORE SERVICES READY[/bold white]"
    )
    console.print(
        "  [dim white]Generating secure session link...[/dim white]\n"
    )
