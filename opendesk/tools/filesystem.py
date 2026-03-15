import os
from typing import Optional
from .registry import register_tool



# Safety: only allow paths within the user's home directory
HOME_DIR = os.path.expanduser("~")

def _is_safe_path(filepath: str) -> bool:
    """Check if the given path is within the user's home directory."""
    abs_path = os.path.abspath(os.path.expanduser(filepath))
    return abs_path.startswith(HOME_DIR)

@register_tool("read_file")
def read_file(filepath: str) -> str:
    """Reads the contents of a file. Only allows paths within the user's home directory."""
    if not _is_safe_path(filepath):
        return f"Access denied: '{filepath}' is outside your home directory ({HOME_DIR})."
    try:
        abs_path = os.path.abspath(os.path.expanduser(filepath))
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Truncate if very large
        if len(content) > 5000:
            content = content[:5000] + "\n...[truncated]"
        return f"File '{abs_path}' contents:\n{content}"
    except Exception as e:
        return f"Error reading file '{filepath}': {e}"

@register_tool("write_file")
def write_file(filepath: str, content: str) -> str:
    """Writes text content to a file. Only allows paths within the user's home directory."""
    if not _is_safe_path(filepath):
        return f"Access denied: '{filepath}' is outside your home directory ({HOME_DIR})."
    try:
        abs_path = os.path.abspath(os.path.expanduser(filepath))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File saved successfully at {abs_path}"
    except Exception as e:
        return f"Error writing to file '{filepath}': {e}"

@register_tool("list_directory")
def list_directory(directory_path: str = "") -> str:
    """Lists files and folders in a directory with file sizes. Defaults to user's home directory."""
    if not directory_path:
        directory_path = HOME_DIR
    
    if not _is_safe_path(directory_path):
        return f"Access denied: '{directory_path}' is outside your home directory ({HOME_DIR})."
    
    try:
        abs_path = os.path.abspath(os.path.expanduser(directory_path))
        items = os.listdir(abs_path)
        if not items:
            return f"Directory '{abs_path}' is empty."
        
        lines = []
        for item in sorted(items):
            full_path = os.path.join(abs_path, item)
            if os.path.isdir(full_path):
                lines.append(f"  [DIR]  {item}")
            else:
                try:
                    size = os.path.getsize(full_path)
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    lines.append(f"  [FILE] {item} ({size_str})")
                except OSError:
                    lines.append(f"  [FILE] {item}")
        
        return f"Contents of '{abs_path}':\n" + "\n".join(lines)
    except Exception as e:
        return f"Error listing directory '{directory_path}': {e}"
@register_tool("share_file")
def share_file(filename: str, search_dir: Optional[str] = None) -> str:
    """Finds a file by name on the PC and prepares it for sharing via Telegram.
    Searches in prioritized folders (Downloads, Desktop, Documents) across all drives.
    """
    import string
    
    # 1. Prioritized current user locations
    prioritized_paths = [
        os.path.join(HOME_DIR, "Downloads"),
        os.path.join(HOME_DIR, "Desktop"),
        os.path.join(HOME_DIR, "Documents"),
    ]
    
    # If user provided a search_dir, put it at the top
    if search_dir:
        # Check if it's a relative path in home or a full path
        if not os.path.isabs(search_dir):
            prioritized_paths.insert(0, os.path.join(HOME_DIR, search_dir))
        else:
            prioritized_paths.insert(0, search_dir)

    # Helper for case-insensitive search
    def find_in_path(base_path: str, target_name: str):
        if not os.path.exists(base_path):
            return None
        # Walk just 2 levels deep for speed, then fall back to glob if needed
        for root, dirs, files in os.walk(base_path):
            # Check depth
            depth = root[len(base_path):].count(os.sep)
            if depth > 2:
                # Limit recursive depth for performance
                dirs[:] = [] # stop recursion here
                continue
                
            for f in files:
                if f.lower() == target_name.lower():
                    return os.path.join(root, f)
        return None

    # Step A: Search Prioritized Paths
    for path in prioritized_paths:
        found = find_in_path(path, filename)
        if found:
            return f"File shared successfully at {found}"

    # Step B: Scan Other Drives (Slow Fallback)
    drive_letters = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    for drive in drive_letters:
        # Skip C: if already searched user folders (to avoid redundant slow scan)
        # We search common root-level folders on other drives
        common_folders = ["Downloads", "Documents", "Desktop", "Photos", "Videos"]
        for folder in common_folders:
            folder_path = os.path.join(drive, folder)
            found = find_in_path(folder_path, filename)
            if found:
                return f"File shared successfully at {found}"

    return f"Could not find {filename} in {search_dir or 'common locations (Downloads, Desktop, Documents)'}."
