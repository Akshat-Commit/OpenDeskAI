import os
import subprocess
import tempfile
from loguru import logger
from opendesk.tools.registry import register_tool



@register_tool("run_python_script")
def run_python_script(code: str) -> str:
    """
    Executes raw Python code on the host machine and returns the stdout/stderr.
    Use this strictly for complex requests that cannot be solved by Layer 1 APIs 
    or Layer 2 PowerShell commands. 
    """
    logger.info("Executing dynamic Python script via Layer 3 interpreter...")
    
    # Create a temporary file to hold the script
    try:
        # Get a temp file path that is auto-cleaned up on close (conceptually, but we do it manually)
        fd, path = tempfile.mkstemp(suffix=".py", text=True)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(code)
            
        # Execute it with a 30 second timeout to prevent infinite loops 
        result = subprocess.run(  # noqa: S603
            ["python", path],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.getcwd()
        )
        
        # Cleanup
        try:
            os.remove(path)
        except OSError:
            pass
            
        output = result.stdout.strip()
        error = result.stderr.strip()
        
        if result.returncode == 0:
            return f"Script executed successfully.\nOutput:\n{output}"
        else:
            return f"Script failed (Exit {result.returncode}).\nError:\n{error}\nOutput:\n{output}"
            
    except subprocess.TimeoutExpired:
        try:
            os.remove(path) # type: ignore
        except:  # noqa: S110
             pass
        return "Script execution timed out after 30 seconds. Infinite loop?"
    except Exception as e:
        return f"Failed to execute Python script: {str(e)}"
