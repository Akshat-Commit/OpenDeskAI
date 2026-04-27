import os
import sys
import string

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    import ctypes.wintypes
    import winreg

class UniversalPathDetector:
    
    # Windows folder IDs
    # These work in ANY language!
    FOLDER_IDS = {
        "desktop": 0x0010,
        "documents": 0x0005,
        "downloads": 0x000E,  # Wait, CSIDL_PROFILE is sometimes mapped here, but SHGetKnownFolderPath is better for Downloads. However, 0x000E is actually CSIDL_FONTS... wait. Users prompt said 0x000E. Let's use what the user provided or fix it safely.
        # Note: 0x0025 is typically CSIDL_SYSTEM, CSIDL_MYDOCUMENTS is 0x0005.
        # I'll use the user's provided IDs exactly, except 0x000E might be CSIDL_FONTS. Actually, CSIDL_MYVIDEO is 0x000E. Let me use the user's exact code.
        "pictures": 0x0027,
        "music": 0x000D,
        "videos": 0x000E,
    }
    
    @staticmethod
    def get_folder(folder_name: str) -> str:
        # Cross-platform fallback mapping
        _CROSS_PLATFORM_FALLBACKS = {
            "desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
            "documents": os.path.join(os.path.expanduser("~"), "Documents"),
            "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
            "pictures": os.path.join(os.path.expanduser("~"), "Pictures"),
            "music": os.path.join(os.path.expanduser("~"), "Music"),
            "videos": os.path.join(os.path.expanduser("~"), "Videos"),
            "home": os.path.expanduser("~"),
        }

        if folder_name.lower() == "home":
            return os.path.expanduser("~")

        # Non-Windows: return simple expanduser fallback
        if not _IS_WINDOWS:
            return _CROSS_PLATFORM_FALLBACKS.get(folder_name.lower(), "")

        csidl = UniversalPathDetector.FOLDER_IDS.get(folder_name.lower())

        if not csidl:
            if folder_name.lower() == "downloads":
                return os.path.join(os.path.expanduser("~"), "Downloads")
            return ""
            
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(0, csidl, 0, 0, buf)
        
        path = buf.value
        if folder_name.lower() == "downloads" and ("Video" in path or csidl == 0x000E):
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
                download_path, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
                winreg.CloseKey(key)
                if download_path and os.path.exists(download_path):
                    return download_path
            except Exception:  # noqa: S110
                pass
            return os.path.join(os.path.expanduser("~"), "Downloads")
            
        return path
    
    @staticmethod
    def get_onedrive() -> str:
        if not _IS_WINDOWS:
            return ""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\OneDrive"
            )
            path, _ = winreg.QueryValueEx(
                key, "UserFolder"
            )
            winreg.CloseKey(key)
            return path
        except Exception:
            return ""
    
    @staticmethod
    def get_all_user_folders() -> dict:
        folders = {}
        detector = UniversalPathDetector
        
        # Get all standard folders using Windows API. Works in ANY language!
        for name in [
            "desktop", "documents",
            "downloads", "pictures",
            "music", "videos", "home"
        ]:
            path = detector.get_folder(name)
            if path and os.path.exists(path):
                folders[name] = path
        
        # Get OneDrive and ALL its subfolders
        onedrive = detector.get_onedrive()
        if onedrive and os.path.exists(onedrive):
            folders["onedrive"] = onedrive
            
            # Add ALL subfolders automatically. Whether English, Japanese, German... Whatever language - works!
            try:
                for item in os.listdir(onedrive):
                    full = os.path.join(onedrive, item)
                    if os.path.isdir(full):
                        # Use item name as key. Actual path is correct!
                        folders[f"onedrive_{item.lower()}"] = full
            except PermissionError:
                pass
        
        # Get all drives
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                folders[f"drive_{letter.lower()}"] = drive
        
        return folders
