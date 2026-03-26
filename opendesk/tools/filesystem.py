import os
from typing import Optional
from .registry import register_tool
from opendesk.utils.file_indexer import file_indexer



from opendesk.utils.path_detector import UniversalPathDetector

# Safety: only allow paths within the user's home directory
HOME_DIR = UniversalPathDetector.get_folder("home") or os.path.expanduser("~")
DESKTOP_PATH = UniversalPathDetector.get_folder("desktop") or os.path.join(HOME_DIR, "Desktop")


def _is_safe_path(filepath: str) -> bool:
    """Check if the given path is within the user's home directory."""
    # Convert 'desktop' or 'Desktop' to the actual discovered path
    if filepath.lower() == "desktop":
        abs_path = DESKTOP_PATH
    else:
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
def list_directory(directory_path: str = "", files_only: bool = False) -> str:
    """Lists files and folders in a directory with file sizes. Defaults to user's home directory. Use 'desktop' to see desktop files. Set files_only=True to hide subdirectories."""
    if not directory_path:
        directory_path = HOME_DIR
    elif directory_path.lower() == "desktop":
        directory_path = DESKTOP_PATH
    
    if not _is_safe_path(directory_path):
        return f"Access denied: '{directory_path}' is outside your home directory ({HOME_DIR})."
    
    try:
        abs_path = os.path.abspath(os.path.expanduser(directory_path))
        items = os.listdir(abs_path)
        if not items:
            return f"Directory '{abs_path}' is empty."
        
        lines = []
        for item in sorted(items):
            # Skip common hidden/system files that clutter output
            if item.lower() in ["desktop.ini", "ntuser.dat", "thumbs.db", ".ds_store"]:
                continue
                
            full_path = os.path.join(abs_path, item)
            is_dir = os.path.isdir(full_path)
            
            if is_dir:
                if not files_only:
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
        
        if not lines:
            return f"No {'files' if files_only else 'items'} found in '{abs_path}'."
            
        return f"Contents of '{abs_path}':\n" + "\n".join(lines)
    except Exception as e:
        return f"Error listing directory '{directory_path}': {e}"
@register_tool("share_file")
def share_file(
    filename: str,
    search_dir: Optional[str] = None
) -> str:
    
    # Step 1: Check index first (instant!)
    results = file_indexer.find_file(filename)
    
    if results:
        # Filter by search_dir if provided
        if search_dir:
            filtered = [
                r for r in results
                if search_dir.lower() in 
                r[1].lower()
            ]
            if filtered:
                return (
                    f"File shared successfully"
                    f" at {filtered[0][0]}"
                )
        else:
            return (
                f"File shared successfully"
                f" at {results[0][0]}"
            )
    
    # Step 2: Live scan as fallback
    # (if index not built yet)
    
    def find_in_path(base_path: str, target_name: str):
        if not os.path.exists(base_path):
            return None
        for root, dirs, files in os.walk(base_path):
            depth = root[len(base_path):].count(os.sep)
            if depth > 2:
                dirs[:] = []
                continue
            for f in files:
                if f.lower() == target_name.lower():
                    return os.path.join(root, f)
        return None

    known_paths = (
        file_indexer.get_all_known_paths()
    )
    
    paths_to_scan = []
    
    # Prioritize search_dir if provided
    if search_dir:
        actual_dir = UniversalPathDetector.get_folder(search_dir.lower())
        if actual_dir:
            paths_to_scan.append(actual_dir)
        elif not os.path.isabs(search_dir):
            paths_to_scan.append(os.path.join(HOME_DIR, search_dir))
        else:
            paths_to_scan.append(search_dir)
            
    # Add all other known paths
    for name, info in known_paths.items():
        if info["path"] not in paths_to_scan:
            paths_to_scan.append(info["path"])
            
    for path in paths_to_scan:
        found = find_in_path(path, filename)
        if found:
            return (
                f"File shared successfully"
                f" at {found}"
            )
    
    return f"Could not find {filename} anywhere."

@register_tool("open_path")
def open_path(path: str) -> str:
    """Opens a file or folder using the system's default application. Only allows paths within the user's home directory."""
    if not _is_safe_path(path):
        return f"Access denied: '{path}' is outside your home directory ({HOME_DIR})."
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(abs_path):
            return f"Error: Path '{abs_path}' does not exist."
        
        # Use os.startfile on Windows for the most reliable 'open with default'
        os.startfile(abs_path) # noqa: S606
        return f"Successfully opened '{abs_path}' using the system default handler."
    except Exception as e:
        return f"Error opening path '{path}': {e}"
