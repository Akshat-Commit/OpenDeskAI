import typer
import os
import sys
import subprocess
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional

# Detect headless mode (running via PM2 / no interactive terminal)
IS_HEADLESS = not sys.stdout.isatty()

app = typer.Typer(
    name="opendesk",
    help="OpenDesk AI - Control your laptop from Telegram",
    add_completion=False,
    rich_markup_mode="rich",
    add_help_option=False,
    pretty_exceptions_show_locals=False,
)

console = Console()

@app.callback(invoke_without_command=True)
def root_main(
    ctx: typer.Context,
    help: bool = typer.Option(
        False, "--help", "-h",
        help="📘 Show the OpenDesk help menu and available commands.",
        is_eager=True
    )
):
    """
    OpenDesk AI Command Line Interface
    """
    if help:
        from rich.console import Console
        Console().print(ctx.get_help())
        raise typer.Exit()

def check_venv():
    venv_python = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        ".venv", "Scripts", "python.exe"
    )
    return venv_python if os.path.exists(
        venv_python
    ) else sys.executable

@app.command()
def setup():
    """
    🛠️ Complete first-time setup wizard.
    Installs and configures everything
    automatically.
    """
    from opendesk.setup_wizard import run_setup
    run_setup()

@app.command()
def start(
    mode: Optional[str] = typer.Option(
        None,
        "--mode", "-m",
        help="AI mode: local, cloud, developer"
    ),
    debug: bool = typer.Option(
        False,
        "--debug", "-d",
        help="Enable debug logging"
    )
):
    """
    🚀 Start OpenDesk agent and show QR code.
    """
    
    if not os.path.exists(".env"):
        console.print(
            "[yellow]No configuration found!\n"
            "Running setup wizard first...[/]\n"
        )
        from opendesk.setup_wizard import run_setup
        run_setup()
        return
    
    current_mode = mode or os.getenv("USER_MODE", "local").lower()
    os.environ["USER_MODE"] = current_mode # Ensure it's set for the rest of the app
    
    if debug:
        os.environ["LOG_LEVEL"] = "DEBUG"
        if not IS_HEADLESS:
            console.print(
                "  [dim grey70]Debug mode active[/]"
            )
    
    try:
        from opendesk.main import run_opendesk
        run_opendesk()
    except KeyboardInterrupt:
        console.print(
            "\n  [yellow]OpenDesk stopped.[/]"
        )
    except Exception as e:
        console.print(
            f"\n  [red]Error: {e}[/]"
        )
        raise typer.Exit(1)

@app.command()
def stop():
    """
    🛑 Stop the running OpenDesk agent.
    """
    console.print(
        "\n  [yellow]Stopping OpenDesk...[/]"
    )
    
    try:
        import psutil
        stopped = False
        
        for proc in psutil.process_iter(
            ['pid', 'name', 'cmdline']
        ):
            try:
                cmdline = proc.info.get(
                    'cmdline', []
                ) or []
                # Strict check: only kill the real OpenDesk agent entrypoint,
                # not any process that happens to mention "opendesk" in args.
                is_agent = any(
                    str(c).endswith('opendesk\\main.py') or
                    str(c).endswith('opendesk/main.py') or
                    str(c).lower() in ('opendesk', 'opendesk.exe')
                    for c in cmdline
                )
                if is_agent and proc.pid != os.getpid():
                    proc.terminate()
                    stopped = True
                    console.print(
                        f"  [green]✅ Stopped "
                        f"process {proc.pid}[/]"
                    )
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied
            ):
                pass
        
        if stopped:
            console.print(
                "\n  [green]OpenDesk stopped![/]"
            )
        else:
            console.print(
                "\n  [yellow]No running "
                "OpenDesk found.[/]"
            )
            
    except Exception as e:
        console.print(f"  [red]Error: {e}[/]")

@app.command()
def status():
    """
    📊 Check OpenDesk system health status.
    """
    from opendesk.utils.banner import show_banner
    show_banner()

@app.command()
def config(
    reset: bool = typer.Option(
        False,
        "--reset",
        help="Reset all configuration"
    )
):
    """
    ⚙️ Configure OpenDesk settings.
    """
    console.print(
        "\n[bold bright_cyan]"
        "OpenDesk Configuration[/]\n"
    )
    
    env_path = ".env"
    existing = {}
    
    if os.path.exists(env_path) and not reset:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()
    
    console.print(
        "[bold white]Step 1:[/] "
        "Telegram Bot Token"
    )
    console.print(
        "  Get from @BotFather on Telegram\n"
    )
    
    current_token = existing.get(
        "TELEGRAM_BOT_TOKEN", ""
    )
    if current_token:
        console.print(
            f"  Current: {current_token[:10]}..."
            f" [dim](press Enter to keep)[/]"
        )
    
    token = typer.prompt(
        "  Enter Bot Token",
        default=current_token or "",
        hide_input=True
    )
    
    console.print(
        "\n[bold white]Step 2:[/] "
        "Bot Username"
    )
    username = typer.prompt(
        "  Enter Bot Username (without @)",
        default=existing.get(
            "TELEGRAM_BOT_USERNAME", ""
        )
    )
    
    console.print(
        "\n[bold white]Step 3:[/] "
        "Your Telegram ID"
    )
    console.print(
        "  Message @userinfobot "
        "on Telegram to get your ID\n"
    )
    telegram_id = typer.prompt(
        "  Enter your Telegram ID",
        default=existing.get(
            "ALLOWED_TELEGRAM_ID", ""
        )
    )
    
    console.print(
        "\n[bold white]Step 4:[/] "
        "Choose AI Mode"
    )
    console.print(
        "  1. [green]LOCAL[/]  - Private, offline,"
        " no API keys needed"
    )
    console.print(
        "  2. [cyan]CLOUD[/]  - Faster, needs"
        " free Groq API key"
    )
    
    mode_choice = typer.prompt(
        "  Enter choice",
        default="1"
    )
    
    if mode_choice == "1":
        user_mode = "local"
        console.print(
            "\n  [green]LOCAL mode selected![/]"
        )
        
        # Auto detect RAM and suggest model
        try:
            import psutil
            ram_gb = (
                psutil.virtual_memory().total
                / (1024 ** 3)
            )
            
            if ram_gb >= 12:
                recommended = "gemma3:12b"
            else:
                recommended = "gemma3:4b"
                
            console.print(
                f"\n  Your RAM: "
                f"[cyan]{ram_gb:.0f}GB[/]"
            )
            console.print(
                f"  Recommended model: "
                f"[cyan]{recommended}[/]"
            )
            
            install_model = typer.confirm(
                f"\n  Download {recommended} now?",
                default=True
            )
            
            if install_model:
                console.print(
                    f"\n  [yellow]Downloading "
                    f"{recommended}...[/]"
                )
                console.print(
                    "  This may take a few minutes."
                )
                subprocess.run(  # noqa: S603
                    ["ollama", "pull", recommended]  # noqa: S607
                )
                
        except Exception as e:
            recommended = "gemma3:12b"
            
        groq_key = ""
        
    else:
        user_mode = "cloud"
        console.print(
            "\n  [cyan]CLOUD mode selected![/]"
        )
        console.print(
            "  Get free Groq API key at:"
            " [link]https://console.groq.com[/]\n"
        )
        groq_key = typer.prompt(
            "  Enter Groq API Key",
            default=existing.get(
                "GROQ_API_KEY_1", ""
            ),
            hide_input=True
        )
        recommended = "llama-3.3-70b-versatile"
    
    # Write .env file
    env_content = f"""# OpenDesk Configuration
# Generated by opendesk config

# Telegram Settings
BOT_TOKEN={token}
BOT_USERNAME={username}
ALLOWED_TELEGRAM_ID={telegram_id}

# AI Mode: local, cloud, developer
USER_MODE={user_mode}

# Ollama Settings
OLLAMA_MODEL_NAME={recommended}
OLLAMA_HOST=http://localhost:11434
OLLAMA_VISION_MODEL_NAME=moondream

# API Keys (optional for local mode)
GROQ_API_KEY_1={groq_key}
GROQ_API_KEY_2=
GEMINI_API_KEY=
GITHUB_API_KEY=
NVIDIA_API_KEY=
"""
    
    with open(env_path, "w") as f:
        f.write(env_content)
    
    console.print(
        "\n[bold green]"
        "✅ Configuration saved![/]"
    )
    console.print(
        "\n[bold white]Run OpenDesk:[/]"
    )
    console.print(
        "  [bold bright_cyan]"
        "opendesk start[/]\n"
    )

@app.command()
def logs(
    lines: int = typer.Option(
        50,
        "--lines", "-n",
        help="Number of lines to show"
    ),
    follow: bool = typer.Option(
        False,
        "--follow", "-f",
        help="Follow log output"
    ),
    errors: bool = typer.Option(
        False,
        "--errors", "-e",
        help="Show only errors"
    )
):
    """
    📋 View OpenDesk logs.
    """
    log_file = "logs/opendesk.log"
    error_file = "logs/errors.log"
    
    target = error_file if errors else log_file
    
    if not os.path.exists(target):
        console.print(
            f"[yellow]No log file found at"
            f" {target}[/]"
        )
        raise typer.Exit()
    
    if follow:
        console.print(
            f"[cyan]Following {target}..."
            "[/] (Ctrl+C to stop)\n"
        )
        try:
            subprocess.run(  # noqa: S603
                ["powershell", "-command",  # noqa: S607
                 f"Get-Content {target} -Wait -Tail {lines}"]
            )
        except KeyboardInterrupt:
            pass
    else:
        with open(target) as f:
            all_lines = f.readlines()
        
        recent = all_lines[-lines:]
        for line in recent:
            line = line.strip()
            if "ERROR" in line:
                console.print(
                    f"[red]{line}[/]"
                )
            elif "WARNING" in line:
                console.print(
                    f"[yellow]{line}[/]"
                )
            elif "INFO" in line:
                console.print(
                    f"[green]{line}[/]"
                )
            else:
                console.print(line)

@app.command()
def version():
    """
    ℹ️ Show OpenDesk version information.
    """
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2)
    )
    
    table.add_column(style="bold cyan")
    table.add_column(style="white")
    
    table.add_row("OpenDesk", "v1.0.0")
    table.add_row("Python", sys.version.split()[0])
    table.add_row(
        "Platform", sys.platform
    )
    
    try:
        import langchain
        table.add_row(
            "LangChain",
            langchain.__version__
        )
    except Exception:  # noqa: S110
        pass
    
    try:
        result = subprocess.run(
            ["ollama", "--version"],  # noqa: S607
            capture_output=True,
            text=True
        )
        if result.stdout:
            table.add_row(
                "Ollama",
                result.stdout.strip()
            )
    except:
        table.add_row(
            "Ollama",
            "Not installed"
        )
    
    console.print(
        Panel(
            table,
            title="[bold bright_cyan]"
            "OpenDesk Version Info[/]",
            border_style="bright_cyan"
        )
    )

@app.command()
def update():
    """
    🔄 Update OpenDesk to latest version.
    """
    console.print(
        "\n[cyan]Updating OpenDesk...[/]\n"
    )
    
    try:
        subprocess.run(  # noqa: S603
            [sys.executable, "-m", "pip",
             "install", "--upgrade", "opendesk"],
            check=True
        )
        console.print(
            "\n[green]✅ OpenDesk updated![/]"
        )
    except Exception as e:
        console.print(
            f"[red]Update failed: {e}[/]"
        )

def main():
    app()

if __name__ == "__main__":
    main()
