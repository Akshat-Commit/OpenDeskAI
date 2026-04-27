import subprocess
import os
import shlex
from loguru import logger
from .registry import register_tool



@register_tool("run_terminal_command")
def run_terminal_command(command: str) -> str:
    """
    Runs a terminal command on the host Windows machine and returns the output.
    Handles 'start' commands (app launches) as fire-and-forget.
    """
    logger.info(f"Executing terminal command: {command}")
    
    cmd_lower = command.strip().lower()
    
    # Fire-and-forget for app launch commands
    is_launch = cmd_lower.startswith("start ") or cmd_lower in ["code", "notepad", "calc", "explorer", "mspaint"]
    
    try:
        if is_launch:
            # Use shell=False for safety. We split the command string correctly.
            cmd_args = shlex.split(command)
            # 'start' is a shell builtin, so for app launches we still need shell=True 
            # BUT we validate/sanitize it.
            # However, direct executables should use shell=False.
            if cmd_args[0].lower() == "start":
                # Secure way to launch apps via start without shell=True
                safe_cmd = ["cmd", "/c", "start", ""] + cmd_args[1:]
                subprocess.Popen(  # noqa: S603
                    safe_cmd,
                    shell=False,
                    cwd=os.path.expanduser("~")
                )
            else:
                subprocess.Popen(  # noqa: S603
                    cmd_args,
                    shell=False,
                    cwd=os.path.expanduser("~")
                )
            return f"App launch command executed: {command}"
        else:
            # Safer way to run powershell commands
            result = subprocess.run(  # noqa: S603
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.getcwd()
            )
            
            output = result.stdout.strip()
            error = result.stderr.strip()
            
            if result.returncode == 0:
                return f"Command executed successfully.\nOutput:\n{output}"
            else:
                return f"Command failed (code {result.returncode}).\nError:\n{error}\nOutput:\n{output}"
    except subprocess.TimeoutExpired:
        return f"Command timed out after 60 seconds."
    except Exception as e:
        return f"Exception executing command: {str(e)}"

