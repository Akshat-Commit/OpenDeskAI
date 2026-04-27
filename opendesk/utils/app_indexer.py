import os
import sqlite3
import threading
import winreg
import time
from loguru import logger
from datetime import datetime
from typing import Optional, Dict, List
from thefuzz import fuzz

class AppIndexer:
    def __init__(self, db_path="opendesk.db"):
        self.db_path = db_path
        self.is_indexing = False
        
        self.APP_ALIASES = {
            "chrome": ["google chrome", "chrome", "browser", "google"],
            "spotify": ["spotify", "music player", "spotify music"],
            "vscode": ["vs code", "visual studio code", "code editor", "vscode"],
            "notepad": ["notepad", "text editor", "note"],
            "calculator": ["calculator", "calc"],
            "whatsapp": ["whatsapp", "whatsapp desktop"],
            "telegram": ["telegram", "telegram desktop"],
            "vlc": ["vlc", "media player", "video player"],
            "word": ["microsoft word", "word", "ms word"],
            "excel": ["microsoft excel", "excel", "ms excel"],
            "powerpoint": ["powerpoint", "ms powerpoint", "presentation"],
        }
        
        self._setup_db()
    
    def _setup_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_index (
                id INTEGER PRIMARY KEY,
                app_name TEXT NOT NULL,
                app_aliases TEXT,
                exe_path TEXT UNIQUE NOT NULL,
                source TEXT,
                last_verified TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_app_name ON app_index(app_name)")
        conn.commit()
        conn.close()

    def _get_aliases_for_app(self, app_name: str) -> str:
        app_lower = app_name.lower()
        for key, aliases in self.APP_ALIASES.items():
            if key in app_lower or any(alias in app_lower for alias in aliases):
                return ",".join(aliases)
        return ""

    def _save_app(self, app_name: str, exe_path: str, source: str) -> bool:
        if not exe_path.lower().endswith('.exe') or not os.path.exists(exe_path):
            return False
            
        # Skip system internals
        skip_words = ['uninstall', 'update', 'setup', 'svchost', 'redist']
        if any(w in exe_path.lower() for w in skip_words) or any(w in app_name.lower() for w in skip_words):
            return False

        aliases = self._get_aliases_for_app(app_name)
        
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO app_index 
                (app_name, app_aliases, exe_path, source, last_verified)
                VALUES (?, ?, ?, ?, ?)
            """, (
                app_name,
                aliases,
                exe_path,
                source,
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.debug(f"Failed to save app {app_name}: {e}")
            return False
        finally:
            conn.close()

    def _scan_registry(self):
        logger.debug("Scanning registry for apps...")
        count = 0
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
            )
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    sub_key_name = winreg.EnumKey(key, i)
                    sub_key = winreg.OpenKey(key, sub_key_name)
                    exe_path, _ = winreg.QueryValueEx(sub_key, "")
                    
                    app_name = sub_key_name.replace(".exe", "")
                    if self._save_app(app_name, exe_path, "registry"):
                        count += 1
                        
                    winreg.CloseKey(sub_key)
                except Exception as e:
                    logger.debug(f"Failed to parse registry key: {e}")
                    continue
            winreg.CloseKey(key)
        except Exception as e:
            logger.debug(f"Registry scan error: {e}")
        return count

    def _scan_start_menu(self):
        logger.debug("Scanning Start Menu for apps...")
        count = 0
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        
        start_paths = [
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
            os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
        ]
        
        for base_path in start_paths:
            if not os.path.exists(base_path):
                continue
                
            for root, _, files in os.walk(base_path):
                for file in files:
                    if file.endswith(".lnk"):
                        try:
                            lnk_path = os.path.join(root, file)
                            shortcut = shell.CreateShortCut(lnk_path)
                            exe_path = shortcut.Targetpath
                            
                            app_name = os.path.splitext(file)[0]
                            if self._save_app(app_name, exe_path, "startmenu"):
                                count += 1
                        except Exception as e:
                            logger.debug(f"Failed to scan startmenu item {app_name}: {e}")
                            continue
        return count

    def _scan_desktop(self):
        logger.debug("Scanning Desktops for apps...")
        count = 0
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        
        from opendesk.utils.path_detector import UniversalPathDetector
        personal_desktop = UniversalPathDetector.get_folder("desktop")
        
        desktop_paths = [r"C:\Users\Public\Desktop"]
        if personal_desktop:
            desktop_paths.append(personal_desktop)
        
        for base_path in desktop_paths:
            if not os.path.exists(base_path):
                continue
                
            for file in os.listdir(base_path):
                if file.endswith(".lnk"):
                    try:
                        lnk_path = os.path.join(base_path, file)
                        shortcut = shell.CreateShortCut(lnk_path)
                        exe_path = shortcut.Targetpath
                        
                        app_name = os.path.splitext(file)[0]
                        if self._save_app(app_name, exe_path, "desktop"):
                            count += 1
                    except Exception as e:
                        logger.debug(f"Failed to scan desktop shortcut {app_name}: {e}")
                        continue
        return count

    def _scan_all_sources(self):
        if self.is_indexing:
            return
            
        self.is_indexing = True
        logger.debug("Started background app indexing...")
        start_time = time.time()
        
        try:
            # Check if we need to re-index (every 24h)
            conn = sqlite3.connect(self.db_path)
            last_app = conn.execute("SELECT last_verified FROM app_index LIMIT 1").fetchone()
            conn.close()
            
            if last_app:
                last_time = datetime.strptime(last_app[0], "%Y-%m-%d %H:%M")
                if (datetime.now() - last_time).days < 1:
                    logger.debug("App index is fresh. Skipping scan.")
                    self.is_indexing = False
                    return

            total = 0
            # Order matters: Registry is highest exactness
            total += self._scan_registry()
            total += self._scan_desktop()
            total += self._scan_start_menu()
            
            duration = time.time() - start_time
            logger.debug(f"App indexing complete in {duration:.1f}s. Indexed {total} apps.")
        except Exception as e:
            logger.error(f"App indexing failed: {e}")
        finally:
            self.is_indexing = False

    def start_background_indexing(self):
        thread = threading.Thread(
            target=self._scan_all_sources,
            daemon=True,
            name="AppIndexer"
        )
        thread.start()
        logger.debug("App indexer started in background")

    def find_app(self, app_name: str) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Step 1: Check exact match or alias instantly
        result = conn.execute("""
            SELECT exe_path FROM app_index
            WHERE LOWER(app_name) = LOWER(?)
            OR LOWER(app_aliases) LIKE LOWER(?)
        """, (app_name, f"%{app_name}%")).fetchone()
        
        if result:
            conn.close()
            return result["exe_path"]
            
        # Step 2: Fuzzy match
        all_apps = conn.execute("SELECT app_name, exe_path FROM app_index").fetchall()
        conn.close()
        
        best_match = None
        best_score = 0
        
        for app in all_apps:
            score = fuzz.ratio(app_name.lower(), app["app_name"].lower())
            if score > best_score:
                best_score = score
                best_match = app
                
        if best_match and best_score > 70:
            return best_match["exe_path"]
            
        return None

    def get_all_apps(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        apps = conn.execute("SELECT app_name, exe_path FROM app_index ORDER BY app_name").fetchall()
        conn.close()
        return [dict(app) for app in apps]

# Global instance
app_indexer = AppIndexer()
