import qrcode # type: ignore
from loguru import logger
import sys
import shutil
from rich.console import Console

from opendesk.config import BOT_USERNAME
from opendesk.utils.session_manager import create_session

_console = Console()

def generate_session_qr(ngrok_url: str, ui=None) -> str:
    """
    Generates a new session and prints a QR code to the terminal.
    Returns the generated session token.
    """
    if not BOT_USERNAME:
        logger.warning("BOT_USERNAME not set. Showing direct-connect instructions instead.")
        if sys.stdout.isatty():
            cols = shutil.get_terminal_size().columns
            _console.print()
            _console.print("─" * cols, style="dim grey70")
            _console.print("      [bold white]NO QR CODE — DIRECT CONNECTION MODE[/bold white]")
            _console.print("      [dim grey70]BOT_USERNAME is not set in .env[/dim grey70]")
            _console.print()
            _console.print("      [bold white]How to connect:[/bold white]")
            _console.print("      [green]1.[/green] Open Telegram and find your bot")
            _console.print("      [green]2.[/green] Send:  [bold white]/start[/bold white]")
            _console.print("      [green]3.[/green] Enter your PIN when prompted (if set)")
            _console.print()
            _console.print("─" * cols, style="dim grey70")
            _console.print()
        return ""
        
    token = create_session(ngrok_url)
    
    # Construct the deep link URL for Telegram
    bot_url = f"https://t.me/{BOT_USERNAME}?start={token}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(bot_url)
    qr.make(fit=True)
    
    import io
    
    # Capture the QR code and print it with a left margin
    f = io.StringIO()
    qr.print_ascii(out=f, invert=True)
    qr_str = f.getvalue()
    
    from rich.text import Text
    if ui:
        for line in qr_str.split("\n"):
            if line.strip() or line:
                ui.add_renderable(Text("      " + line, no_wrap=True))
                
        ui.add_renderable(Text())
        ui.add_renderable(Text.from_markup("      [bold white]SCAN WITH PHONE CAMERA TO CONNECT[/bold white]"))
        ui.add_renderable(Text.from_markup("      [dim grey70]Link expires in 60 seconds.[/dim grey70]"))
        ui.add_renderable(Text())
    else:
        for line in qr_str.split("\n"):
            if line.strip() or line:
                print("      " + line)
        
        cols = shutil.get_terminal_size().columns
        print("\n" + "─" * cols)
        print("      SCAN WITH PHONE CAMERA TO CONNECT")
        print("      Link expires in 60 seconds.")
        print("─" * cols + "\n")
    
    return token
