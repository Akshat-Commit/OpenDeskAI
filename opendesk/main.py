import sys
import os
import time

# Ensure the root directory is in sys.path so 'opendesk' is recognized as a package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opendesk.config import USER_MODE
from opendesk.utils.banner import (
    show_banner, 
    show_mode_banner, 
    show_health_header, 
    show_health_footer, 
    show_completion_banner,
    console
)

# Show the professional ASCII banner first
show_banner()

# Show the red mode activation message
if USER_MODE:
    show_mode_banner(USER_MODE)

from loguru import logger
    
# Configure Loguru
os.makedirs("logs", exist_ok=True)
logger.remove()  # Remove default handler
logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", level="INFO")
logger.add("logs/opendesk.log", rotation="10 MB", retention="5 days", compression="zip", level="DEBUG")

from opendesk.bot import run_bot # type: ignore

from opendesk.db import db
from opendesk.utils.context_monitor import monitor_instance
from opendesk.utils.qr_generator import generate_session_qr

def setup_cloudflare():
    """Starts a Cloudflare TryCloudflare tunnel to expose the local bot without session limits."""
    from pycloudflared import try_cloudflare # type: ignore
    import sys
    
    logger.info("Starting Cloudflare Tunnel...")
    try:
        # try_cloudflare starts a background subprocess handling the cloudflared binary
        # and returns a highly reliable https://*.trycloudflare.com URL routing to port 5000
        tunnel = try_cloudflare(port=5000)
        public_url = tunnel.tunnel
        logger.info(f"Cloudflare tunnel active at: {public_url}")
        return public_url, tunnel
    except Exception as e:
        logger.error(f"Failed to start Cloudflare tunnel: {e}")
        print("\n[!] ERROR: Could not start Cloudflare tunnel. Check your internet connection.")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OpenDesk AI Tool")
    parser.add_argument("command", nargs="?", default="start", help="Command to run: start, config, status")
    args = parser.parse_args()
    
    cmd = args.command.lower()
    
    if cmd == "config":
        from opendesk.setup_wizard import run_setup_wizard
        run_setup_wizard()
        sys.exit(0)
        
    elif cmd == "status":
        from opendesk.health_check import run_health_checks
        import asyncio
        if asyncio.run(run_health_checks()):
            show_completion_banner()
        else:
            sys.exit(1)
            console.print("\n  [bold red]🔴 ISSUES DETECTED[/bold red]\n")
        sys.exit(0)
        
    elif cmd == "start":
        # ===== PRE-FLIGHT LINT CHECK (catches syntax errors before they crash the bot) =====
        import subprocess
        from opendesk.health_check import AnimatedSpinner
        
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
            
            lint_result = subprocess.run(
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
                time.sleep(0.5) # Slight pause to show the success icon per phase
                spinner.stop(f"{message.split(' ')[1].capitalize()} passed", status="success")
                
        if not all_passed:
            print("\nFix these errors before starting the bot.")
            sys.exit(1)

        
        # ===== SETUP WIZARD (first-run config) =====
        from opendesk.setup_wizard import detect_user_mode, run_setup_wizard
        from opendesk.config import USER_MODE
        
        if not USER_MODE:
            mode = detect_user_mode()
            if mode:
                # If we detected a mode, we should probably run the wizard or set it
                run_setup_wizard()
                from importlib import reload
                import opendesk.config
                reload(opendesk.config)
        else:
            # We already showed the mode banner at the very top
            pass

        
        from opendesk.health_check import run_health_checks    
        import asyncio
        logger.info("Running pre-flight health checks...")
        
        if not asyncio.run(run_health_checks()):
            logger.error("Health checks failed. Please check the logs.")
            sys.exit(1)
            
        show_health_footer()
        show_completion_banner()
            
        # Start Cloudflare Tunnel silently if needed
        cf_url, cf_tunnel = setup_cloudflare()
        
        # Generate Session and QR Code
        generate_session_qr(cf_url)
        
        logger.info("Starting ContextMonitor Background Thread...")
        monitor_instance.start()
        
        logger.info("Starting Telegram Bot Polling...")
        try:
            run_bot()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            logger.info("Stopping ContextMonitor...")
            monitor_instance.stop()
            
            logger.info("Shutting down Cloudflare Tunnel...")
            try:
                from pycloudflared import stop_cloudflared # type: ignore
                stop_cloudflared(cf_tunnel.port)
            except Exception:
                pass
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
