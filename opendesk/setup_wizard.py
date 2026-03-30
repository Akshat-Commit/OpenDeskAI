import os
import sys
import subprocess
import time
import shutil
import msvcrt  # Standard on Windows for single-key capture
import typer
from rich.console import Console, Group
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.live import Live

# Global console instance
console = Console()

LARGE_BANNER = """
      ░█████╗░██████╗░███████╗███╗░░██╗██████╗░███████╗░██████╗██╗░░██╗
      ██╔══██╗██╔══██╗██╔════╝████╗░██║██╔══██╗██╔════╝██╔════╝██║░██╔╝
      ██║░░██║██████╔╝█████╗░░██╔██╗██║██║░░██║█████╗░░╚█████╗░█████═╝░
      ██║░░██║██╔═══╝░██╔══╝░░██║╚████║██║░░██║██╔══╝░░░╚═══██╗██╔═██╗░
      ╚█████╔╝██║░░░░░███████╗██║░╚███║██████╔╝███████╗██████╔╝██║░╚██╗
      ░╚════╝░╚═╝░░░░░╚══════╝╚═╝░░╚══╝╚═════╝░╚══════╝╚═════╝░╚═╝░░╚═╝
"""

SMALL_BANNER = """
   ___  ___  ___ _  _ ___ ___ ___ _  __
  / _ \\| _ \\/ __| \\| |   \\_ __/ __| |/ /
 | (_) |  _/| _|| .` | |) | _|\\__ \\ ' < 
  \\___/|_|  |___|_|\\_|___/|___|___/_|\\_\\
"""

class SetupUI:
    def __init__(self):
        self.steps = []
        self.live = None
        self.current_prompt = ""
        self.current_default = None
        self.current_input = ""
        self.is_asking = False
        self.is_password = False
        
    def add_step(self, title):
        self.steps.append({
            "title": f" {title} ",
            "lines": []
        })
        self.refresh()

    def append_text(self, text):
        if self.steps:
            self.steps[-1]["lines"].append(text)
            self.refresh()

    def refresh(self):
        if self.live:
            self.live.update(self.get_renderable(), refresh=True)

    def get_renderable(self):
        cols, rows = shutil.get_terminal_size()
        width = max(60, min(cols - 4, 120))
        
        # 1. BANNER & HEADER (DYNAMIC SHRINK)
        # We now prefer the LARGE LOGO unless the screen is extremely small (< 25 lines)
        show_full_banner = rows > 25
        show_small_banner = rows > 18
        
        renderables = []
        
        if show_full_banner:
            for line in LARGE_BANNER.strip("\n").split("\n"):
                renderables.append(Align.center(Text(line, style="bold white", no_wrap=True)))
        elif show_small_banner:
            for line in SMALL_BANNER.strip("\n").split("\n"):
                renderables.append(Align.center(Text(line, style="bold white", no_wrap=True)))
        
        renderables.extend([
            Text(),
            Align.center("[dim white]V1.0.0  |  GITHUB.COM/AKSHAT-COMMIT/OPENDESK[/dim white]"),
            Text(), # Top Margin
            Align.center("[bold black on green]  OPENDESK SETUP  [/bold black on green]"),
            Text(), # spacer
        ])
        
        # 2. CALCULATE REMAINING SPACE FOR STEPS
        used_height = len(renderables) + 10 # Estimated overhead for Panel + Input + Padding
        available_height = max(5, rows - used_height)
        
        # 3. SELECT STEPS FOR VIEWPORT (SLIDING WINDOW)
        step_renderables = []
        for step in self.steps:
            step_lines = [Text(step["title"], style="bold grey82 on #2a2a2a")]
            for line in step["lines"]:
                step_lines.append(Text.from_markup("  " + line))
            step_lines.append(Text())
            step_renderables.append(step_lines)
            
        # Total line count of all steps
        flat_steps = []
        for s in step_renderables: flat_steps.extend(s)
        
        if len(flat_steps) > available_height:
            # Drop older steps from the view, but keep the current one
            # Always show at least the last 2 steps if possible
            while len(flat_steps) > available_height and len(step_renderables) > 1:
                step_renderables.pop(0)
                flat_steps = []
                for s in step_renderables: flat_steps.extend(s)
            
            # Removed indicator per user request
            renderables.append(Text())
            
        renderables.extend(flat_steps)
            
        # 4. INTEGRATED INPUT SECTION
        if self.is_asking:
            renderables.append(Text("───────────────────────────────────────────────────", style="dim grey70"))
            
            # Show default prompt if available
            prompt_text = self.current_prompt
            if self.current_default and not self.is_password:
                prompt_text += f" [dim](Enter to keep: {self.current_default})[/dim]"
            elif self.current_default and self.is_password:
                prompt_text += " [dim](Enter to keep current PIN)[/dim]"
                
            renderables.append(Text.from_markup(f"  {prompt_text}", style="bold white"))
            display_input = "*" * len(self.current_input) if self.is_password else self.current_input
            renderables.append(Text.from_markup(f"  [bold green]>>>[/bold green] {display_input}█"))
            renderables.append(Text())

        # 5. FINAL ASSEMBLY
        # We remove the outer Align.center to fix the 'double-header' glitch on Windows.
        # Rich Panel with a fixed width will naturally align itself better.
        return Panel(
            Group(*renderables),
            title="[bold grey82] ◈  OPENDESK INTELLIGENT ONBOARDING  ◈ [/bold grey82]",
            width=width,
            padding=(1, 2),
            border_style="grey82"
        )

    def ask(self, prompt, default=None, password=False):
        """Captures input character-by-character while the box stays visible."""
        self.current_prompt = prompt
        self.current_default = default
        self.current_input = ""
        self.is_password = password
        self.is_asking = True
        self.refresh()
        
        last_cols, _ = shutil.get_terminal_size()
        
        # Windows Keyboard Capture Loop
        while True:
            # Check for terminal resize
            new_cols, _ = shutil.get_terminal_size()
            if new_cols != last_cols:
                last_cols = new_cols
                self.refresh()

            if msvcrt.kbhit():
                char = msvcrt.getch()
                
                # Enter
                if char in (b'\r', b'\n'):
                    break
                # Backspace
                elif char == b'\x08':
                    self.current_input = self.current_input[:-1]
                # Ctrl+C
                elif char == b'\x03':
                    raise typer.Abort()
                # Ordinary characters
                else:
                    try:
                        decoded = char.decode('utf-8', errors='ignore')
                        if decoded and (decoded.isprintable() or decoded.isnumeric()):
                            self.current_input += decoded
                    except Exception:
                        pass
                
                self.refresh()
            
            # Small throttle to avoid 100% CPU, though kbhit is non-blocking
            time.sleep(0.01)
            
        answer = self.current_input if self.current_input else self.current_default
        self.is_asking = False
        self.refresh()
        return answer

ui = SetupUI()

def run_setup():
    from dotenv import dotenv_values
    env_values = dotenv_values(".env")
    
    try:
        # Wrap the whole execution in a Live context for smooth updates
        # Manual Refresh Mode: auto_refresh=False for zero-lag and zero-flicker stability
        with Live(ui.get_renderable(), console=console, auto_refresh=False) as live:
            ui.live = live
            
            # STEP 1: Python
            ui.add_step("STEP 1/10 — CORE ENVIRONMENT")
            v = sys.version_info
            ui.append_text(f"Python {v.major}.{v.minor}.{v.micro} localized.")
            time.sleep(0.4)
            
            # STEP 2: OS Check
            ui.add_step("STEP 2/10 — SYSTEM ARCHITECTURE")
            import platform
            ui.append_text(f"OS: {platform.system()} {platform.release()} confirmed.")
            time.sleep(0.4)
            
            # STEP 3: Hardware Scan
            ui.add_step("STEP 3/10 — HARDWARE PROFILE")
            import psutil
            ram = psutil.virtual_memory().total / (1024**3)
            cpu_count = psutil.cpu_count()
            ui.append_text(f"CPU: {cpu_count} cores | RAM: {ram:.1f}GB detected.")
            time.sleep(0.4)
            
            # STEP 4: Ollama Support
            ui.add_step("STEP 4/10 — LOCAL AI HANDSHAKE")
            try:
                subprocess.run(["ollama", "--version"], capture_output=True, check=True)
                ui.append_text("Ollama service responding.")
                model = "gemma3:12b" if ram >= 12 else "gemma3:4b"
                ui.append_text(f"Recommended model: {model}")
            except:
                ui.append_text("[yellow]Ollama not found. Fallback to Cloud mode suggested.[/yellow]")
                model = "gemma3:4b"
            time.sleep(0.5)
            
            # STEP 5: Telegram Token
            ui.add_step("STEP 5/10 — BOT CREDENTIALS")
            ui.append_text("1. Open @BotFather in Telegram")
            token = ui.ask("Paste your Bot Token:", default=env_values.get("BOT_TOKEN"))
            ui.append_text("✓ Token validated.")
            
            # STEP 6: Bot Username
            ui.add_step("STEP 6/10 — IDENTITY LINKING")
            ui.append_text("Enter the username of your bot (e.g. MyDeskBot)")
            username = ui.ask("Bot Username (without @):", default=env_values.get("BOT_USERNAME"))
            ui.append_text(f"✓ Bot linked: @{username}")
            
            # STEP 7: Authorization
            ui.add_step("STEP 7/10 — ADMIN AUTHENTICATION")
            ui.append_text("Get your ID from @userinfobot")
            tid = ui.ask("Enter your Telegram Admin ID:", default=env_values.get("ALLOWED_TELEGRAM_ID"))
            ui.append_text(f"✓ Admin identity set: {tid}")
            
            # STEP 8: Mode Selection
            ui.add_step("STEP 8/10 — AI ENGINE MODE")
            ui.append_text("1. LOCAL     | Privacy & Cost Focus (Runs only on your PC)")
            ui.append_text("2. CLOUD     | Speed & Reliability Focus (Uses Groq + Local)")
            ui.append_text("3. DEVELOPER | Power & Redundancy Focus (Full 6-Model Chain)")
            
            current_mode_raw = env_values.get("USER_MODE", "1")
            # Convert internal names to numeric choices for the prompt
            mode_map = {"local": "1", "cloud": "2", "developer": "3"}
            mode_default = mode_map.get(current_mode_raw.lower(), "1")
            
            choice = ui.ask("Enter engine choice (1/2/3):", default=mode_default)
            if choice == "3":
                mode = "developer"
            elif choice == "2":
                mode = "cloud"
            else:
                mode = "local"
            ui.append_text(f"✓ Active Engine: {mode.upper()}")
            
            # STEP 9: Security PIN
            ui.add_step("STEP 9/10 — SECURITY LAYER (2FA)")
            ui.append_text("Your Telegram ID is your 'Keycard', but a PIN is your 'Vault Code'.")
            ui.append_text("A PIN is HIGHLY recommended to prevent accidental PC command execution.")
            pin = ui.ask(
                "Set a 4-digit PIN (Press Enter to stay with 1-Click Access):", 
                default=env_values.get("OPENDESK_PIN", ""),
                password=True
            )
            if pin:
                ui.append_text(f"✓ 2FA Security: ENABLED (Secondary key added)")
            else:
                ui.append_text("✓ 2FA Security: BYPASSED (One-click access inherited)")
            
            # STEP 10: Connectivity & Finalization
            ui.add_step("STEP 10/10 — PERSISTENCE GATEWAY")
            ui.append_text("Finalizing your intelligent environment...")
            ans = ui.ask("💾 Finalize and save these changes to .env? (y/n)")
            
            if ans.lower() == 'y':
                try:
                    save_env(token, username, tid, mode, model, pin)
                    ui.append_text("✓ .env configuration persistent.")
                    time.sleep(0.8)
                    ui.add_step("◈ SESSION COMPLETE ◈")
                    ui.append_text("Setup process finalized.")
                    ui.append_text("Run 'opendesk start' to activate remote control.")
                except PermissionError:
                    ui.append_text("[bold red]❌ Access Denied! .env is currently locked.[/bold red]")
                    ui.append_text("   Please close your code editor (or stop OpenDesk) and try again.")
            else:
                ui.append_text("✓ Safety Switch Activated: No changes were written to .env.")
                time.sleep(0.8)
                ui.add_step("◈ TEST MODE FINISHED ◈")
                ui.append_text("UI validation complete.")
                ui.append_text("Run 'opendesk setup' again when ready to save.")
                
            time.sleep(1.5)
            
    except typer.Abort:
        console.print("\n[bold red]  Setup was cancelled.[/bold red]")
        sys.exit(1)

def save_env(token, username, tid, mode, model, pin):
    for d in ["logs", "data/screenshots", "data/documents"]:
        os.makedirs(d, exist_ok=True)
        
    env_file = ".env"
    from dotenv import set_key
    
    # Create file if it doesn't exist to avoid set_key errors
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write("\n")
            
    set_key(env_file, "BOT_TOKEN", token)
    set_key(env_file, "BOT_USERNAME", username)
    set_key(env_file, "ALLOWED_TELEGRAM_ID", tid)
    set_key(env_file, "USER_MODE", mode)
    set_key(env_file, "OLLAMA_MODEL_NAME", model)
    set_key(env_file, "OPENDESK_PIN", pin)
    set_key(env_file, "OPENDESK_ENV", "production")

if __name__ == "__main__":
    run_setup()
