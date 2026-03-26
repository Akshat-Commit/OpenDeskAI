import sys
import os
import time

# Ensure the root directory is in sys.path so 'opendesk' is recognized as a package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opendesk.config import USER_MODE
from opendesk.utils.banner import (
    show_banner, 
    show_mode_banner, 
    show_health_footer, 
    show_completion_banner,
    console
)

from opendesk.utils.file_indexer import file_indexer
from opendesk.utils.app_indexer import app_indexer
from loguru import logger
    
# Configure Loguru
os.makedirs("logs", exist_ok=True)
logger.remove()  # Remove default handler

from opendesk.config import USER_MODE

# Smart Logging: Show deep python tracebacks to devs, hide them from standard users to keep UI clean
is_dev = (USER_MODE == "developer")
console_level = "DEBUG" if is_dev else os.environ.get("LOG_LEVEL", "WARNING")

if console_level == "DEBUG":
    logger.add(
        sys.stderr, 
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", 
        level="DEBUG", 
        backtrace=True, 
        diagnose=is_dev
    )
else:
    logger.add(
        sys.stderr, 
        format="<level>{message}</level>", 
        level=console_level, 
        backtrace=False, 
        diagnose=False
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
                print("      " + line)
                
        public_url = tunnel.tunnel
        logger.debug(f"Cloudflare tunnel active at: {public_url}")
        return public_url, tunnel
    except Exception as e:
        logger.error(f"Failed to start Cloudflare tunnel: {e}")
        print("\n[!] ERROR: Could not start Cloudflare tunnel. Check your internet connection.")
        sys.exit(1)

def run_opendesk():
    """Main entry point to start the full OpenDesk agent services."""
    import subprocess
    import asyncio
    from opendesk.health_check import AnimatedSpinner, run_health_checks
    
    # Show the professional ASCII banner first
    show_banner()
    
    # Show the red mode activation message
    if USER_MODE:
        show_mode_banner(USER_MODE)

    
    # ===== PRE-FLIGHT LINT CHECK =====
    phases = [
        ("Linting core agent...", ["opendesk/ollama_agent/"]),
        ("Checking tool definitions...", ["opendesk/tools/"]),
        ("Verifying bot interface...", ["opendesk/bot.py", "opendesk/main.py"]),
        ("Analyzing database logic...", ["opendesk/db/"]),
    ]
    
    all_passed = True
    for message, paths in phases:
        spinner = AnimatedSpinner(message)
        spinner.start()
        
        lint_result = subprocess.run(  # noqa: S603
            ["ruff", "check"] + paths + ["--select", "F821"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        if lint_result.returncode != 0:
            spinner.stop(f"Errors found in {message.split(' ')[1]}", status="error")
            print(lint_result.stdout)
            all_passed = False
            break
        else:
            time.sleep(0.5)
            spinner.stop(f"{message.split(' ')[1].capitalize()} passed", status="success")
            
    if not all_passed:
        print("\nFix these errors before starting the bot.")
        sys.exit(1)

    # ===== SETUP WIZARD (first-run config) =====
    from opendesk.setup_wizard import detect_user_mode, run_setup_wizard
    
    if not USER_MODE:
        mode = detect_user_mode()
        if mode:
            run_setup_wizard()
            from importlib import reload
            import opendesk.config
            reload(opendesk.config)
            
    # ===== BACKGROUND INDEXERS =====
    spinner = AnimatedSpinner("Waking up background indexers...")
    spinner.start()
    file_indexer.start_background_indexing()
    app_indexer.start_background_indexing()
    time.sleep(0.5)
    spinner.stop("Indexers running in background", status="success")
    
    # ===== HEALTH CHECKS =====
    logger.debug("Running pre-flight health checks...")
    if not asyncio.run(run_health_checks()):
        logger.error("Health checks failed. Please check the logs.")
        console.print("  [red]Health checks failed. Check logs for details.[/red]")
        sys.exit(1)
        
    show_health_footer()
    
    # ===== CLOUDFLARE TUNNEL =====
    spinner = AnimatedSpinner("Opening secure Cloudflare tunnel...")
    spinner.start()
    cf_url, cf_tunnel = setup_cloudflare()
    spinner.stop("Tunnel connected successfully", status="success")
    
    # ===== BOT STARTUP (Background) =====
    monitor_instance.start()
    
    # ===== FINAL READINESS =====
    show_completion_banner()
    
    # ===== QR GENERATION =====
    time.sleep(0.5)  # brief pause for UX flow
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
        console.print("\n  [yellow]Shutting down securely...[/yellow]")
    finally:
        console.print("  [dim]Cleaning up background tasks...[/dim]")
        file_indexer.stop_watcher()
        monitor_instance.stop()
        try:
            from pycloudflared import stop_cloudflared # type: ignore
            stop_cloudflared(cf_tunnel.port)
        except Exception:  # noqa: S110
            pass
