import sys
import os
import time

# Force UTF-8 encoding on Windows so Rich/loguru Unicode doesn't crash under PM2
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure the root directory is in sys.path so 'opendesk' is recognized as a package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.live import Live
from rich.text import Text
from loguru import logger


from opendesk.utils.banner import (
    show_banner, 
    show_mode_banner, 
    show_completion_banner,
    set_live_active,
    console
)

from opendesk.utils.file_indexer import file_indexer
from opendesk.utils.app_indexer import app_indexer
from opendesk.utils.startup_ui import StartupUI, IS_HEADLESS
    
# Configure Loguru
os.makedirs("logs", exist_ok=True)
logger.remove()  # Remove default handler


# Smart Logging: Show deep python tracebacks to devs on crash, hide them from standard users to keep UI clean
is_dev = (os.environ.get("USER_MODE", "developer").lower() == "developer")
console_level = os.environ.get("LOG_LEVEL", "INFO" if is_dev else "WARNING")

# Display format adjustments
format_string = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>" 
    if console_level == "DEBUG" 
    else "<level>{message}</level>"
)

logger.add(
    sys.stderr, 
    format=format_string, 
    level=console_level, 
    backtrace=is_dev, 
    diagnose=is_dev
)

# File logger always catches everything deeply
logger.add("logs/opendesk.log", rotation="10 MB", retention="5 days", compression="zip", level="DEBUG", backtrace=True, diagnose=True)

# Register global exception handler so total crashes are printed beautifully in the console for developers
def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).error("Uncaught Critical Crash:")

sys.excepthook = global_exception_handler

from opendesk.utils.context_monitor import monitor_instance
from opendesk.utils.qr_generator import generate_session_qr

def setup_cloudflare():
    """Starts a Cloudflare TryCloudflare tunnel to expose the local bot without session limits."""
    from pycloudflared import try_cloudflare # type: ignore
    import sys
    import io
    
    logger.debug("Starting Cloudflare Tunnel...")
    try:
        # Intercept pycloudflared's hardcoded print statements to add our UI margin
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()
        
        try:
            tunnel = try_cloudflare(port=5000)
        finally:
            sys.stdout = old_stdout
            
        # Pad the intercepted output
        for line in captured.getvalue().split("\n"):
            if line.strip():
                logger.debug("Cloudflare: " + line.strip())
                
        public_url = tunnel.tunnel
        logger.debug(f"Cloudflare tunnel active at: {public_url}")
        return public_url, tunnel
    except Exception as e:
        logger.error(f"Failed to start Cloudflare tunnel: {e}")
        print("\n[!] ERROR: Could not start Cloudflare tunnel. Check your internet connection.")
        sys.exit(1)

async def send_startup_notification(bot):
    try:
        import os
        from datetime import datetime
        
        chat_id_str = os.getenv("ALLOWED_TELEGRAM_ID")
        if not chat_id_str:
            return
        chat_id = int(chat_id_str)
        time_now = datetime.now().strftime("%I:%M %p")
        
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "🖥️ *OpenDesk is Online!*\n\n"
                "Your laptop is ready.\n\n"
                "📱 *Connect from anywhere:*\n"
                "Just send /start to this bot\n\n"
                f"⏰ Started at: {time_now}\n"
                "🔒 Only you can access this."
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Could not send startup notification: {e}")

async def keep_proxy_alive():
    """Pings the cloud proxy every 10 min to prevent Render sleep."""
    import aiohttp
    import asyncio
    proxy_url = os.getenv("OPENDESK_PROXY_URL", "").rstrip("/")
    if not proxy_url:
        return
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(600)
            try:
                async with session.get(f"{proxy_url}/") as resp:
                    logger.info(f"Proxy ping: {resp.status}")
            except Exception as e:
                logger.warning(f"Proxy ping failed: {e}")

def run_opendesk():
    """Main entry point to start the full OpenDesk agent services."""
    import subprocess
    import asyncio
    from opendesk.health_check import run_health_checks
    from opendesk.utils.instance_lock import acquire_lock
    # Read USER_MODE HERE (after cli.py has set os.environ["USER_MODE"])
    from opendesk.config import USER_MODE
    
    # 0. Acquire system lock to prevent multiple instances
    _lock_handle = acquire_lock()
    
    ui = None
    live = None

    if not IS_HEADLESS:
        set_live_active(True)  # Suppress direct console.print during Live
        console.clear()        # Clean slate — prevents double-banner artifact
        ui = StartupUI()
        live = Live(ui.get_renderable(), console=console, auto_refresh=False)
        live.start()
        ui.live = live
        from opendesk.utils.banner import get_banner_renderable, get_mode_renderable
        ui.add_renderable(get_banner_renderable())
        if USER_MODE:
            ui.add_renderable(get_mode_renderable(USER_MODE))
    else:
        # Fallback for logs/non-interactive terminals
        show_banner()
        if USER_MODE:
            show_mode_banner(USER_MODE)

    
    # ===== SECTION HEADERS =====
    if ui:
        ui.add_renderable(Text())
        ui.add_renderable(Text.from_markup("      [bold black on white] OPENDESK CORE SERVICES [/bold black on white]"))
        ui.add_renderable(Text())
    
    phases = [
        ("Checking tool definitions...", ["opendesk/tools/"]),
        ("Verifying bot interface...", ["opendesk/bot.py", "opendesk/main.py"]),
        ("Analyzing database logic...", ["opendesk/db/"]),
    ]
    
    all_passed = True
    for message, paths in phases:
        if ui:
            ui.add_renderable(Text.from_markup(f"      [bold white]○[/bold white]  {message}"))
        
        lint_result = subprocess.run(  # noqa: S603
            ["ruff", "check"] + paths + ["--select", "F821"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        if lint_result.returncode != 0:
            if ui:
                ui.update_renderable(Text.from_markup(f"      [bold red]●[/bold red]  Error in {message.split(' ')[1]}"))
            else:
                print(f"Errors found in {message.split(' ')[1]}")
            print(lint_result.stdout)
            all_passed = False
            break
        else:
            time.sleep(0.3)
            label = f"{message.split(' ')[1].capitalize()} passed"
            if ui:
                ui.update_renderable(Text.from_markup(f"      [bold green]●[/bold green]  {label}"))
            else:
                print(f"      ●  {label}")
            
    if not all_passed:
        if live:
            live.stop()
        print("\nFix these errors before starting the bot.")
        sys.exit(1)


            
    # ===== BACKGROUND INDEXERS =====
    if ui:
        ui.add_renderable(Text.from_markup("      [bold white]○[/bold white]  Waking up background indexers..."))
    file_indexer.start_background_indexing()
    app_indexer.start_background_indexing()
    
    # Wait 2 seconds for initial index
    time.sleep(2)
    
    # Check if index has data
    import sqlite3
    try:
        conn = sqlite3.connect("opendesk.db")
        count = conn.execute("SELECT COUNT(*) FROM file_index").fetchone()[0]
        conn.close()
        
        if count > 0:
            if ui:
                ui.update_renderable(Text.from_markup(f"      [bold green]●[/bold green]  Indexers running in background ({count} files)"))
            else:
                print(f"      ●  Indexers running in background ({count} files)")
        else:
            if ui:
                ui.update_renderable(Text.from_markup("      [bold green]●[/bold green]  Indexers running in background"))
            else:
                print("      ●  Indexers running in background")
    except Exception as e:
        if ui:
            ui.update_renderable(Text.from_markup("      [bold green]●[/bold green]  Indexers running in background"))
        else:
            print("      ●  Indexers running in background")
    
    # ===== SECTION HEADERS =====
    if ui:
        ui.add_renderable(Text())
        ui.add_renderable(Text.from_markup("      [bold black on white] SYSTEM & STABILITY CHECK [/bold black on white]"))
        ui.add_renderable(Text())
        
    # ===== HEALTH CHECKS =====
    logger.debug("Running pre-flight health checks...")
    if not asyncio.run(run_health_checks(ui=ui)):
        if live:
            live.stop()
        logger.error("Health checks failed. Please check the logs.")
        console.print("  [red]Health checks failed. Check logs for details.[/red]")
        sys.exit(1)
    
    # ===== CLOUDFLARE TUNNEL =====
    if ui:
        ui.add_renderable(Text.from_markup("      [bold white]○[/bold white]  Opening secure tunnel..."))
    cf_url, cf_tunnel = setup_cloudflare()
    if ui:
        ui.update_renderable(Text.from_markup(f"      [bold green]●[/bold green]  Tunnel connected successfully"))
    
    # ===== BOT STARTUP (Background) =====
    monitor_instance.start()
    
    # ===== FINAL READINESS =====
    if ui:
        ui.add_renderable(Text.from_markup("\n      [bold green]●[/bold green] [bold white]OPENDESK CORE SERVICES READY[/bold white]"))
        ui.add_renderable(Text.from_markup("      [dim grey70]Generating secure session link...[/dim grey70]\n"))
        time.sleep(0.5)
        # Generate QR completely inside the UI Box
        token = generate_session_qr(cf_url, ui=ui)
        if live:
            live.stop()
            set_live_active(False)  # Resume normal console output
    else:
        show_completion_banner()
        token = generate_session_qr(cf_url)
    
    try:
        from opendesk.config import USER_MODE as CURRENT_MODE
        if CURRENT_MODE == "server":
            import uvicorn
            from opendesk.server import app
            uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)  # noqa: S104
        else:
            from opendesk.bot import run_bot
            run_bot()
    except KeyboardInterrupt:
        console.print("\n      [yellow]Shutting down securely...[/yellow]")
    finally:
        console.print("      [dim]Cleaning up background tasks...[/dim]")
        file_indexer.stop_watcher()
        monitor_instance.stop()
        try:
            from pycloudflared import stop_cloudflared # type: ignore
            stop_cloudflared(cf_tunnel.port)
        except Exception:  # noqa: S110
            pass
