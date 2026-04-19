import os
from loguru import logger
from .registry import register_tool



from opendesk.utils.path_detector import UniversalPathDetector

# Safety: only allow paths within the user's home directory
HOME_DIR = UniversalPathDetector.get_folder("home") or os.path.expanduser("~")
DESKTOP_PATH = UniversalPathDetector.get_folder("desktop") or os.path.join(HOME_DIR, "Desktop")


def _is_safe_path(filepath: str) -> bool:
    """Check if the given path is within the user's home directory."""
    lower_path = filepath.lower().strip()
    if lower_path in ["desktop", "downloads", "documents", "pictures", "music", "videos"]:
        abs_path = UniversalPathDetector.get_folder(lower_path)
        if not abs_path:
            abs_path = os.path.join(HOME_DIR, lower_path.capitalize())
    else:
        abs_path = os.path.abspath(os.path.expanduser(filepath))
    return abs_path.startswith(HOME_DIR)

@register_tool("read_file")
def read_file(filepath: str) -> str:
    """Reads the contents of a file. Only allows paths within the user's home directory."""
    if not _is_safe_path(filepath):
        return f"Access denied: '{filepath}' is outside your home directory ({HOME_DIR})."
    try:
        lower_path = filepath.lower().strip()
        if lower_path in ["desktop", "downloads", "documents", "pictures", "music", "videos"]:
            abs_path = UniversalPathDetector.get_folder(lower_path) or os.path.join(HOME_DIR, lower_path.capitalize())
        else:
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
        import re
        abs_path = os.path.abspath(os.path.expanduser(filepath))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        # Clean markdown if forced to right to .txt
        if abs_path.lower().endswith(".txt"):
            content = re.sub(r'\*\*(.*?)\*\*', r'\1', content) # bold
            content = re.sub(r'__(.*?)__', r'\1', content) # bold
            content = re.sub(r'\*(.*?)\*', r'\1', content) # italic
            content = re.sub(r'_(.*?)_', r'\1', content) # italic
            content = re.sub(r'^#+\s*(.*?)$', r'\n\1\n' + '-'*20, content, flags=re.MULTILINE) # headings
            content = content.replace('```', '')
            
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content.strip())
        return f"File saved successfully at {abs_path}"
    except Exception as e:
        return f"Error writing to file '{filepath}': {e}"

@register_tool("list_directory")
def list_directory(directory_path: str = "", files_only: bool = False) -> str:
    """Lists files and folders in a directory with file sizes. Defaults to user's home directory. Use 'desktop', 'downloads', 'documents', etc. to see fast folders. Set files_only=True to hide subdirectories."""
    if not directory_path:
        directory_path = HOME_DIR
    else:
        lower_path = directory_path.lower().strip()
        if lower_path in ["desktop", "downloads", "documents", "pictures", "music", "videos"]:
            detected = UniversalPathDetector.get_folder(lower_path)
            if detected:
                directory_path = detected
            else:
                directory_path = os.path.join(HOME_DIR, lower_path.capitalize())
    
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
    search_dir: str = None
) -> str:
    """
    Finds a file on the laptop and
    prepares it for sharing via Telegram.
    Searches indexed database first
    then falls back to live scan.
    """
    # METHOD 1: Check file index first
    # This is instant - already indexed!
    try:
        from opendesk.utils.file_indexer import (
            file_indexer
        )
        
        results = file_indexer.find_file(
            filename
        )
        
        if results:
            # Filter by search_dir if given
            if search_dir:
                filtered = [
                    r for r in results
                    if search_dir.lower() in (r[1].lower() if len(r) > 1 else r[0].lower())
                ]
                if filtered:
                    found_path = filtered[0][0]
                    return (
                        f"File shared successfully"
                        f" at {found_path}"
                    )
            else:
                found_path = results[0][0]
                return (
                    f"File shared successfully"
                    f" at {found_path}"
                )
                
    except Exception as e:
        import loguru
        loguru.logger.warning(
            f"File indexer search failed: {e}"
            f" Falling back to live scan..."
        )
    
    # METHOD 2: Use path detector
    # Gets real Windows paths
    def _find_in_path(base_path: str, target_name: str):
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

    try:
        from opendesk.utils.path_detector import (
            UniversalPathDetector
        )
        
        all_paths = (
            UniversalPathDetector
            .get_all_user_folders()
        )
        
        for name, path in all_paths.items():
            if not os.path.exists(path):
                continue
            found = _find_in_path(
                path, filename
            )
            if found:
                return (
                    f"File shared successfully"
                    f" at {found}"
                )
                
    except Exception as e:
        import loguru
        loguru.logger.warning(
            f"Path detector failed: {e}"
        )
    
    # METHOD 3: Basic fallback
    home = os.path.expanduser("~")
    basic_paths = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Pictures"),
        "D:\\",
        "D:\\Downloads",
    ]
    
    for base in basic_paths:
        if os.path.exists(base):
            found = _find_in_path(
                base, filename
            )
            if found:
                return (
                    f"File shared successfully"
                    f" at {found}"
                )
    
    return (
        f"Could not find '{filename}'.\n"
        f"Make sure the filename is correct.\n"
        f"Try: share [exact filename.ext]"
    )

@register_tool("find_file_location")
def find_file_location(
    filename: str
) -> str:
    """
    Finds where a file is located
    on the laptop.
    Use when user asks:
    - where is [file]?
    - which folder has [file]?
    - is [file] in downloads?
    - can you find [file]?
    Returns the full path if found.
    """
    try:
        from opendesk.utils.file_indexer import (
            file_indexer
        )
        results = file_indexer.find_file(
            filename
        )
        
        if results:
            paths_found = []
            for r in results[:3]:
                folder = os.path.dirname(r[0])
                paths_found.append(
                    f"📁 {folder}"
                )
            
            response = (
                f"✅ Found '{filename}':\n"
            )
            response += "\n".join(paths_found)
            return response
        else:
            return (
                f"❌ '{filename}' not found "
                f"in indexed locations.\n"
                f"It might be in an unusual "
                f"folder or not yet indexed."
            )
    except Exception as e:
        return f"Search error: {e}"

@register_tool("read_and_summarize")
def read_and_summarize(
    filename: str
) -> str:
    """
    Finds a file, reads its content
    and returns it for AI to summarize.
    Use when user says:
    - summarize [file]
    - what is in [file]?
    - read [file] for me
    - explain [file]
    """
    try:
        from opendesk.utils.file_indexer import (
            file_indexer
        )
        
        # Check if it's already a valid path
        import os
        if os.path.exists(filename):
            file_path = filename
        else:
            # Find file using indexer
            results = file_indexer.find_file(
                filename
            )
            
            if not results:
                # One last try to just search by the base name if it was a weird path
                base = os.path.basename(filename)
                results = file_indexer.find_file(base)
                if not results:
                    return f"Could not find '{filename}'"
            
            file_path = results[0][0]
        
        ext = os.path.splitext(
            file_path
        )[1].lower()
        
        content = ""
        
        # Read based on file type
        if ext == ".pdf":
            try:
                import PyPDF2
                with open(
                    file_path, "rb"
                ) as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages[:5]:
                        content += (
                            page.extract_text()
                        )
            except:
                content = "Could not read PDF"
                
        elif ext in [".txt", ".py", ".md", ".csv"]:
            with open(
                file_path, "r",
                encoding="utf-8",
                errors="ignore"
            ) as f:
                content = f.read()[:3000]
                
        elif ext == ".docx":
            try:
                from docx import Document
                doc = Document(file_path)
                content = "\n".join([
                    p.text
                    for p in doc.paragraphs
                ])[:3000]
            except:
                content = "Could not read docx"
        else:
            return (
                f"File found at {file_path}\n"
                f"Cannot read {ext} files yet."
            )
        
        if content:
            return (
                f"File: {filename}\n"
                f"Location: {file_path}\n\n"
                f"Content:\n{content[:2000]}"
            )
        else:
            return f"File is empty: {file_path}"
            
    except Exception as e:
        return f"Read error: {e}"


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

@register_tool("find_latest_file")
def find_latest_file(
    file_type: str = "pdf",
    folder: str = "downloads"
) -> str:
    """
    Finds the most recently modified file of a specific type in a folder.
    Use when user says 'latest pdf in downloads', 'most recent file', etc.
    file_type: pdf, docx, jpg, png, txt
    folder: downloads, desktop, documents, pictures
    """
    import sqlite3
    from opendesk.utils.file_indexer import file_indexer

    folder_patterns = {
        "downloads": "%download%",
        "desktop": "%desktop%",
        "documents": "%document%",
        "pictures": "%picture%",
        "onedrive": "%onedrive%",
    }
    
    pattern = folder_patterns.get(folder.lower(), f"%{folder.lower()}%")
    ext = f".{file_type.lower()}" if not file_type.startswith('.') else file_type.lower()
    
    try:
        conn = sqlite3.connect(file_indexer.db_path)
        # Using the file_index SQLite table directly
        results = conn.execute("""
            SELECT filename, filepath, last_modified, size_kb 
            FROM file_index 
            WHERE LOWER(filepath) LIKE ? 
            AND LOWER(extension) = ? 
            ORDER BY last_modified DESC 
            LIMIT 1
        """, (pattern, ext)).fetchall()
        conn.close()
        
        if results:
            filename = results[0][0]
            filepath = results[0][1]
            modified = results[0][2]
            size = results[0][3]
            
            return (
                f"Latest {file_type.upper()} found:\n"
                f"Name: {filename}\n"
                f"Path: {filepath}\n"
                f"Modified: {modified}\n"
                f"Size: {size:.1f} KB"
            )
        
        return f"No recently modified {file_type.upper()} files tracked in {folder}."
            
    except Exception as e:
        return f"Search error in SQLite file index: {str(e)}"


@register_tool("find_files_by_filter")
def find_files_by_filter(
    file_type: str = "pdf",
    time_filter: str = "this week",
    folder: str = "all"
) -> str:
    """
    Finds files of a specific type that were modified within a given time period.
    Use this when user asks things like:
    - 'find all pdf files modified this week'
    - 'which docx files did I work on today?'
    - 'show me images from this month'
    - 'list all pdfs changed recently'

    Parameters:
        file_type  : File extension to search for. E.g. 'pdf', 'docx', 'jpg', 'png', 'txt', 'xlsx'.
        time_filter: One of 'today', 'yesterday', 'this week', 'last week', 'this month', 'last month'.
        folder     : Where to look. E.g. 'downloads', 'documents', 'desktop', 'all' (searches everywhere).
    """
    import datetime
    import sqlite3
    from opendesk.utils.file_indexer import file_indexer

    # ── Resolve time boundaries ──────────────────────────────────────────────
    now = datetime.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    tf = time_filter.lower().strip()
    if tf == "today":
        cutoff = today_start
    elif tf == "yesterday":
        cutoff = today_start - datetime.timedelta(days=1)
        now = today_start  # upper bound = start of today
    elif tf in ("this week", "week"):
        # Monday of the current week
        cutoff = today_start - datetime.timedelta(days=today_start.weekday())
    elif tf in ("last week",):
        this_monday = today_start - datetime.timedelta(days=today_start.weekday())
        cutoff = this_monday - datetime.timedelta(weeks=1)
        now = this_monday
    elif tf in ("this month", "month"):
        cutoff = today_start.replace(day=1)
    elif tf in ("last month",):
        first_of_this_month = today_start.replace(day=1)
        cutoff = (first_of_this_month - datetime.timedelta(days=1)).replace(day=1)
        now = first_of_this_month
    else:
        # Try to parse as N days, e.g. "3 days"
        import re as _re
        m = _re.match(r"(\d+)\s*day", tf)
        if m:
            cutoff = today_start - datetime.timedelta(days=int(m.group(1)))
        else:
            cutoff = today_start - datetime.timedelta(days=7)  # default: one week

    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # ── Resolve folder pattern ────────────────────────────────────────────────
    folder_patterns = {
        "downloads": "%download%",
        "desktop":   "%desktop%",
        "documents": "%document%",
        "pictures":  "%picture%",
        "music":     "%music%",
        "videos":    "%video%",
        "onedrive":  "%onedrive%",
        "all":       "%",
    }
    folder_pattern = folder_patterns.get(folder.lower(), f"%{folder.lower()}%")

    ext = f".{file_type.lower()}" if not file_type.startswith('.') else file_type.lower()

    # ── Live filesystem scan as primary method ────────────────────────────────
    HOME = os.path.expanduser("~")

    # Determine which base directories to scan
    if folder.lower() == "all":
        try:
            scan_roots = list(UniversalPathDetector.get_all_user_folders().values())
        except Exception:
            scan_roots = [
                os.path.join(HOME, "Downloads"),
                os.path.join(HOME, "Desktop"),
                os.path.join(HOME, "Documents"),
                os.path.join(HOME, "Pictures"),
                os.path.join(HOME, "Music"),
                os.path.join(HOME, "Videos"),
                HOME,
            ]
    else:
        detected = UniversalPathDetector.get_folder(folder.lower())
        scan_roots = [detected] if detected else [os.path.join(HOME, folder.capitalize())]

    matches = []
    cutoff_ts = cutoff.timestamp()
    now_ts = now.timestamp()

    for root_dir in scan_roots:
        if not os.path.isdir(root_dir):
            continue
        try:
            for dirpath, _dirs, files in os.walk(root_dir):
                # Limit depth to 4 levels to stay fast
                depth = dirpath[len(root_dir):].count(os.sep)
                if depth > 4:
                    _dirs[:] = []
                    continue
                for fname in files:
                    if not fname.lower().endswith(ext):
                        continue
                    full = os.path.join(dirpath, fname)
                    try:
                        mtime = os.path.getmtime(full)
                    except OSError:
                        continue
                    if cutoff_ts <= mtime <= now_ts:
                        size_bytes = os.path.getsize(full)
                        if size_bytes < 1024:
                            size_str = f"{size_bytes} B"
                        elif size_bytes < 1024 * 1024:
                            size_str = f"{size_bytes / 1024:.1f} KB"
                        else:
                            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                        mod_dt = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                        matches.append((mod_dt, fname, size_str, full))
        except PermissionError:
            continue

    # ── Fallback: SQLite index ────────────────────────────────────────────────
    if not matches:
        try:
            conn = sqlite3.connect(file_indexer.db_path)
            rows = conn.execute("""
                SELECT filename, filepath, last_modified, size_kb
                FROM file_index
                WHERE LOWER(extension) = ?
                  AND LOWER(filepath) LIKE ?
                  AND last_modified >= ?
                  AND last_modified <= ?
                ORDER BY last_modified DESC
                LIMIT 50
            """, (ext, folder_pattern, cutoff_str, now_str)).fetchall()
            conn.close()
            for fname, fpath, mod, size_kb in rows:
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
                matches.append((mod, fname, size_str, fpath))
        except Exception as db_err:
            logger.debug(f"SQLite index fallback failed in find_files_by_filter: {db_err}")

    if not matches:
        return (
            f"No {file_type.upper()} files found that were modified '{time_filter}' "
            f"in '{folder}'.\n"
            f"(Searched from {cutoff_str} to {now_str})"
        )

    # Sort by modification time descending
    matches.sort(key=lambda x: x[0], reverse=True)

    lines = [
        f"[{file_type.upper()}] files modified '{time_filter}' "
        f"({len(matches)} found):\n"
    ]
    for mod_dt, fname, size_str, fpath in matches:
        lines.append(f"  - {fname}  ({size_str})  [modified {mod_dt}]")

    return "\n".join(lines)

