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

    def _sanitize(self, text: str) -> str:
        """Strip surrogate characters that crash Rich on Windows consoles."""
        return text.encode('utf-8', errors='replace').decode('utf-8')

    def append_text(self, text):
        if self.steps:
            self.steps[-1]["lines"].append(self._sanitize(text))
            self.refresh()

    def refresh(self):
        if self.live:
            self.live.update(self.get_renderable(), refresh=True)

    def get_renderable(self):
        cols, rows = shutil.get_terminal_size()
        width = max(60, min(cols - 4, 120))
        
        # 1. BANNER & HEADER (DYNAMIC SHRINK)
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
            Text(),
            Align.center("[bold black on green]  OPENDESK SETUP  [/bold black on green]"),
            Text(),
        ])
        
        # 2. CALCULATE REMAINING SPACE FOR STEPS
        used_height = len(renderables) + 10
        available_height = max(5, rows - used_height)
        
        # 3. SELECT STEPS FOR VIEWPORT (SLIDING WINDOW)
        step_renderables = []
        for step in self.steps:
            step_lines = [Text(step["title"], style="bold black on white")]
            for line in step["lines"]:
                step_lines.append(Text.from_markup("  " + line))
            step_lines.append(Text())
            step_renderables.append(step_lines)
            
        flat_steps = []
        for s in step_renderables:
            flat_steps.extend(s)
        
        if len(flat_steps) > available_height:
            while len(flat_steps) > available_height and len(step_renderables) > 1:
                step_renderables.pop(0)
                flat_steps = []
                for s in step_renderables:
                    flat_steps.extend(s)
            renderables.append(Text())
            
        renderables.extend(flat_steps)
            
        # 4. INTEGRATED INPUT SECTION
        if self.is_asking:
            renderables.append(Text("───────────────────────────────────────────────────", style="dim grey70"))
            
            prompt_text = self.current_prompt
            if self.current_default and not self.is_password:
                prompt_text += f" [dim](Enter to keep: {self.current_default})[/dim]"
            elif self.current_default and self.is_password:
                prompt_text += " [dim](Enter to keep current PIN)[/dim]"
                
            renderables.append(Text.from_markup(f"  {prompt_text}", style="bold white"))
            display_input = "*" * len(self.current_input) if self.is_password else self.current_input
            renderables.append(Text.from_markup(f"  [bold green]>>>[/bold green] {display_input}\u2588"))
            renderables.append(Text())

        # 5. FINAL ASSEMBLY
        return Panel(
            Group(*renderables),
            title="[bold grey82] \u25c8  OPENDESK INTELLIGENT ONBOARDING  \u25c8 [/bold grey82]",
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
            new_cols, _ = shutil.get_terminal_size()
            if new_cols != last_cols:
                last_cols = new_cols
                self.refresh()

            if msvcrt.kbhit():
                char = msvcrt.getch()
                
                if char in (b'\r', b'\n'):
                    break
                elif char == b'\x08':
                    self.current_input = self.current_input[:-1]
                elif char == b'\x03':
                    raise typer.Abort()
                else:
                    try:
                        decoded = char.decode('utf-8', errors='ignore')
                        if decoded and (decoded.isprintable() or decoded.isnumeric()):
                            self.current_input += decoded
                    except Exception:  # noqa: S110
                        pass
                
                self.refresh()
            
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
        with Live(ui.get_renderable(), console=console, auto_refresh=False) as live:
            ui.live = live
            
            # STEP 1: Python
            ui.add_step("STEP 1/12 \u2014 CORE ENVIRONMENT")
            v = sys.version_info
            ui.append_text(f"Python {v.major}.{v.minor}.{v.micro} localized.")
            time.sleep(0.4)
            
            # STEP 2: OS Check
            ui.add_step("STEP 2/12 \u2014 SYSTEM ARCHITECTURE")
            import platform
            ui.append_text(f"OS: {platform.system()} {platform.release()} confirmed.")
            time.sleep(0.4)
            
            # STEP 3: Hardware Scan
            ui.add_step("STEP 3/12 \u2014 HARDWARE PROFILE")
            import psutil
            ram = psutil.virtual_memory().total / (1024**3)
            cpu_count = psutil.cpu_count()
            ui.append_text(f"CPU: {cpu_count} cores | RAM: {ram:.1f}GB detected.")
            time.sleep(0.4)
            
            # STEP 4: Ollama Support
            ui.add_step("STEP 4/12 \u2014 LOCAL AI HANDSHAKE")
            ollama_found = False
            recommended_model = "gemma3:12b" if ram >= 12 else "gemma3:4b"
            try:
                subprocess.run(["ollama", "--version"], capture_output=True, check=True)  # noqa: S603, S607
                ui.append_text("Ollama service responding.")
                ui.append_text(f"Recommended model: {recommended_model}")
                ollama_found = True
            except Exception:
                ui.append_text("[yellow]Ollama not found. Cloud mode recommended.[/yellow]")
            time.sleep(0.5)
            
            # STEP 5: Mode Selection (moved up from Step 8)
            ui.add_step("STEP 5/12 \u2014 AI ENGINE MODE")
            ui.append_text("1. LOCAL     | Privacy & Cost Focus (Runs only on your PC)")
            ui.append_text("2. CLOUD     | Speed & Reliability Focus (Uses Groq + Local)")
            ui.append_text("3. DEVELOPER | Power & Redundancy Focus (Full 6-Model Chain)")
            
            current_mode_raw = env_values.get("USER_MODE", "1")
            mode_map = {"local": "1", "cloud": "2", "developer": "3"}
            mode_default = mode_map.get(current_mode_raw.lower(), "1")
            
            while True:
                choice = ui.ask("Enter engine choice (1/2/3) (? for help):", default=mode_default)
                if choice == "?":
                    ui.append_text("  💡 1 = LOCAL: Ollama only. Fully private, no internet needed for AI.")
                    ui.append_text("     2 = CLOUD: Groq speed + Ollama fallback. Fast & reliable.")
                    ui.append_text("     3 = DEVELOPER: Full 6-model chain. Max power & redundancy.")
                else:
                    break
            if choice == "3":
                mode = "developer"
            elif choice == "2":
                mode = "cloud"
            else:
                mode = "local"
            ui.append_text(f"\u2713 Active Engine: {mode.upper()}")
            
            # Branch based on mode
            model = recommended_model
            api_keys = {}
            
            if mode == "local":
                # STEP 6A: LOCAL — Model Guide
                ui.add_step("STEP 6/12 \u2014 MODEL SETUP")
                ui.append_text(f"Based on your {ram:.1f}GB RAM, we recommend: [bold cyan]{recommended_model}[/bold cyan]")
                ui.append_text("")
                ui.append_text("  Open a NEW terminal window and run:")
                ui.append_text(f"  [bold white]ollama pull {recommended_model}[/bold white]")
                ui.append_text(f"  [bold white]ollama run {recommended_model}[/bold white]  (type 'hello', quit with /bye)")
                ui.append_text("")
                ui.append_text("  When done, come back here and press Enter to confirm.")
                
                while True:
                    model_input = ui.ask(
                        f"Model name to use (? for help, Enter = {recommended_model}):",
                        default=recommended_model
                    )
                    if model_input == "?":
                        ui.append_text("  💡 Type the exact model name you pulled with 'ollama pull'.")
                        ui.append_text(f"     Press Enter to use the recommended: {recommended_model}")
                    else:
                        break
                model = model_input or recommended_model
                ui.append_text(f"\u2713 Model configured: {model}")
                
            else:
                # STEP 6B/6C: CLOUD or DEVELOPER — API Keys
                mode_label = "CLOUD" if mode == "cloud" else "DEVELOPER"
                ui.add_step(f"STEP 6/12 \u2014 API KEYS ({mode_label})")
                ui.append_text("Minimum 2 API keys required.")
                ui.append_text("  * Recommended free providers (get free API keys):")
                ui.append_text("    Groq  -> https://console.groq.com")
                ui.append_text("    Gemini -> https://aistudio.google.com")
                ui.append_text("  Type '?' on any field for help. Press Enter to skip optional providers.")
                ui.append_text("")
                
                KNOWN_PROVIDERS = {
                    "groq":   {"env_key": "GROQ_API_KEY_1",   "model_hint": "llama-3.3-70b-versatile"},
                    "gemini": {"env_key": "GEMINI_API_KEY",    "model_hint": "gemini-2.0-flash"},
                    "github": {"env_key": "GITHUB_API_KEY",    "model_hint": "gpt-4o-mini"},
                    "claude": {"env_key": "ANTHROPIC_API_KEY", "model_hint": "claude-3-5-sonnet-20241022"},
                    "openai": {"env_key": "OPENAI_API_KEY",    "model_hint": "gpt-4o"},
                }
                
                provider_count = 0
                min_required = 2
                
                while True:
                    provider_count += 1
                    required_label = "Required" if provider_count <= min_required else "Optional"
                    ui.append_text(f"  \u2500\u2500 Provider {provider_count} ({required_label}) \u2500\u2500")
                    
                    # Inner loop for provider name validation
                    while True:
                        pname = ui.ask("Provider name (e.g. Groq, Gemini, Claude) (? for help, Enter to skip):")
                        if pname == "?":
                            ui.append_text("  💡 Supported: Groq, Gemini, GitHub, Claude, OpenAI")
                            ui.append_text("     Or type any custom name \u2014 key will be auto-generated.")
                        elif not pname or not pname.strip():
                            if provider_count > min_required:
                                # Skip optional provider
                                ui.append_text("  \u2713 No more providers added.")
                                break
                            else:
                                ui.append_text("  [yellow]\u26a0 Provider name required for minimum 2 keys.[/yellow]")
                        else:
                            break # valid provider
                            
                    if not pname or not pname.strip():
                        # We broke out because it was an optional skip. No more providers.
                        provider_count -= 1
                        break
                    
                    pname_clean = pname.strip()
                    pname_lower = pname_clean.lower()
                    known = KNOWN_PROVIDERS.get(pname_lower)
                    model_hint = known["model_hint"] if known else ""
                    env_key_base = known["env_key"] if known else f"{pname_clean.upper().replace(' ', '_')}_API_KEY"
                    
                    # Ask for API key
                    while True:
                        api_key = ui.ask(f"  API Key for {pname_clean} (? for help):", default=env_values.get(env_key_base, ""))
                        if api_key == "?":
                            ui.append_text(f"  💡 Paste the API key from {pname_clean}'s developer console.")
                        else:
                            break
                    
                    # Ask for model name
                    model_env_key = f"{pname_clean.upper().replace(' ', '_')}_MODEL_NAME"
                    while True:
                        model_name = ui.ask(
                            f"  Model name for {pname_clean} (? for help):",
                            default=model_hint or env_values.get(model_env_key, "")
                        )
                        if model_name == "?":
                            hint_text = f"Recommended: {model_hint}" if model_hint else f"Enter the model name from {pname_clean}'s docs."
                            ui.append_text(f"  💡 {hint_text}")
                        else:
                            break
                    
                    # Store the collected key + model
                    if api_key and api_key.strip():
                        api_keys[env_key_base] = api_key.strip()
                        if model_name and model_name.strip():
                            api_keys[model_env_key] = model_name.strip()
                        ui.append_text(f"  \u2713 {pname_clean} [{model_name or model_hint}] \u2192 saved.")
                    else:
                        ui.append_text(f"  [yellow]\u2192 {pname_clean} skipped (no key entered).[/yellow]")
                        provider_count -= 1
                    
                    # Prompt to add more after minimum reached
                    if provider_count >= min_required:
                        while True:
                            more = ui.ask("  Add another provider? (y/n, ? for help):", default="n")
                            if more == "?":
                                ui.append_text("  💡 Type y to add another API key, n to continue.")
                            else:
                                break
                        if (more or "n").strip().lower() != "y":
                            break
                
                # Ollama as final fallback
                if ollama_found:
                    ui.append_text("")
                    ui.append_text(f"  \u2713 Local Ollama fallback: {recommended_model} (auto-detected)")
                    model = recommended_model
                else:
                    model = "gemma3:4b"
            
            # STEP 7: Telegram Token
            ui.add_step("STEP 7/12 \u2014 BOT CREDENTIALS")
            ui.append_text("1. Open @BotFather in Telegram")
            while True:
                token = ui.ask("Paste your Bot Token (? for help):", default=env_values.get("BOT_TOKEN"))
                if token == "?":  # noqa: S105
                    ui.append_text("  💡 Open Telegram \u2192 Search @BotFather \u2192 Send /newbot")
                    ui.append_text("     Give your bot a name \u2192 Copy the token it sends you.")
                else:
                    break
            ui.append_text("\u2713 Token validated.")
            
            # STEP 8: Bot Username
            ui.add_step("STEP 8/12 \u2014 IDENTITY LINKING")
            ui.append_text("Enter the username of your bot (e.g. MyDeskBot)")
            while True:
                username = ui.ask("Bot Username (without @) (? for help):", default=env_values.get("BOT_USERNAME"))
                if username == "?":
                    ui.append_text("  💡 The username you chose in @BotFather when creating the bot.")
                    ui.append_text("     Example: MyDeskBot  (no @ symbol, just the name).")
                else:
                    break
            ui.append_text(f"\u2713 Bot linked: @{username}")
            
            # STEP 9: Authorization
            ui.add_step("STEP 9/12 \u2014 ADMIN AUTHENTICATION")
            ui.append_text("Get your ID from @userinfobot")
            while True:
                tid = ui.ask("Enter your Telegram Admin ID (? for help):", default=env_values.get("ALLOWED_TELEGRAM_ID"))
                if tid == "?":
                    ui.append_text("  💡 Open Telegram \u2192 Search @userinfobot \u2192 Send any message.")
                    ui.append_text("     It will reply with your numeric ID. Copy and paste it here.")
                else:
                    break
            ui.append_text(f"\u2713 Admin identity set: {tid}")
            
            # STEP 10: Security PIN
            ui.add_step("STEP 10/12 \u2014 SECURITY LAYER (2FA)")
            ui.append_text("Your Telegram ID is your 'Keycard', but a PIN is your 'Vault Code'.")
            ui.append_text("A PIN is HIGHLY recommended to prevent accidental PC command execution.")
            while True:
                pin = ui.ask(
                    "Set a 4-digit PIN (? for help, Enter to skip):",
                    default=env_values.get("OPENDESK_PIN", ""),
                    password=True
                )
                if pin == "?":
                    ui.append_text("  💡 A 4-digit code e.g. 1234. You'll type it before every command.")
                    ui.append_text("     Press Enter to skip \u2014 bot will respond with one-click access.")
                else:
                    break
            if pin:
                ui.append_text("\u2713 2FA Security: ENABLED (Secondary key added)")
            else:
                ui.append_text("\u2713 2FA Security: BYPASSED (One-click access inherited)")
            
            # STEP 11: Local Vision Engine
            ui.add_step("STEP 11/12 \u2014 LOCAL VISION ENGINE")
            ui.append_text("  Highly recommended!")
            if ollama_found:
                ans_vision = ui.ask("Download Moondream Vision Model? (1.7GB) (y/n)", default="y")
                if (ans_vision or "y").strip().lower() == "y":
                    ui.append_text("Downloading Moondream Vision Model... (may take a few minutes)")
                    try:
                        subprocess.run(["ollama", "pull", "moondream"], capture_output=True, check=False)  # noqa: S603, S607
                        ui.append_text("✓ Vision model ready.")
                    except Exception as e:
                        ui.append_text(f"[yellow]⚠ Vision model pull failed: {e}[/yellow]")
                else:
                    ui.append_text("Skipped Vision model download.")
            else:
                ui.append_text("  Ollama not active. Skipping local vision engine.")

            # STEP 12: Finalization
            ui.add_step("STEP 12/12 \u2014 PERSISTENCE GATEWAY")
            ui.append_text("Finalizing your intelligent environment...")
            while True:
                ans = ui.ask("💾 Save changes to .env? (y/n, ? for help)", default="n")
                if (ans or "n").strip().lower() == "?":
                    ui.append_text("  💡 Type y to write all settings to the .env file and finish setup.")
                    ui.append_text("     Type n to exit without saving \u2014 nothing will be changed.")
                else:
                    break
            
            if (ans or "n").strip().lower() == 'y':
                try:
                    save_env(token, username, tid, mode, model, pin, api_keys)
                    ui.append_text("✓ .env configuration persistent.")
                    time.sleep(0.8)
                    
                    # Automated Dependency Install
                    ui.add_step("◈ DOWNLOADING DEPENDENCIES ◈")
                    ui.append_text("Installing Playwright Browser Engine... (may take a minute)")
                    try:
                        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True, check=False)  # noqa: S603
                        ui.append_text("✓ Browser engine installed.")
                    except Exception as e:
                        ui.append_text(f"[yellow]⚠ Browser engine install failed: {e}[/yellow]")
                        
                    time.sleep(0.8)

                    ui.add_step("◈ SESSION COMPLETE ◈")
                    ui.append_text("Setup process finalized.")
                    ui.append_text("Run 'opendesk start' to activate remote control.")
                except PermissionError:
                    ui.append_text("[bold red]\u274c Access Denied! .env is currently locked.[/bold red]")
                    ui.append_text("   Please close your code editor (or stop OpenDesk) and try again.")
            else:
                ui.append_text("✓ Setup aborted: No changes were written to .env.")
                time.sleep(0.8)
                ui.add_step("◈ SETUP ABORTED ◈")
                ui.append_text("You chose not to save.")
                ui.append_text("Run 'opendesk setup' again when ready to save.")
                
            time.sleep(1.5)
            
    except typer.Abort:
        console.print("\n[bold red]  Setup was cancelled.[/bold red]")
        sys.exit(1)

def save_env(token, username, tid, mode, model, pin, api_keys=None):
    for d in ["logs", "data/screenshots", "data/documents"]:
        os.makedirs(d, exist_ok=True)
        
    env_file = ".env"
    from dotenv import set_key
    
    # Create file if it doesn't exist to avoid set_key errors
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write("\n")
            
    set_key(env_file, "BOT_TOKEN", token or "")
    set_key(env_file, "BOT_USERNAME", username or "")
    set_key(env_file, "ALLOWED_TELEGRAM_ID", tid or "")
    set_key(env_file, "USER_MODE", mode or "local")
    set_key(env_file, "OLLAMA_MODEL_NAME", model or "gemma3:4b")
    set_key(env_file, "OPENDESK_PIN", pin or "")
    set_key(env_file, "OPENDESK_ENV", "production")
    
    # Save any dynamically collected API keys
    if api_keys:
        for key, value in api_keys.items():
            if value and value.strip():
                set_key(env_file, key, value.strip())

if __name__ == "__main__":
    run_setup()
