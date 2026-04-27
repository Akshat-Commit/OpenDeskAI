import os
import sqlite3
import threading

from loguru import logger
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class OpenDeskFileWatcher(FileSystemEventHandler):
    
    def __init__(self, indexer):
        self.indexer = indexer
    
    def on_created(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        filename = os.path.basename(filepath)
        
        # Only index relevant extensions
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [
            '.jpg', '.jpeg', '.png', '.gif',
            '.pdf', '.docx', '.xlsx', '.pptx',
            '.txt', '.mp3', '.mp4', '.zip',
            '.exe', '.py', '.csv', '.webp'
        ]:
            return
        
        try:
            size = os.path.getsize(filepath) / 1024
            modified = datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            )
            drive = filepath[:3]
            folder = os.path.dirname(filepath)
            
            conn = sqlite3.connect(
                self.indexer.db_path
            )
            conn.execute("""
                INSERT OR REPLACE INTO file_index
                (filename, filepath, extension,
                size_kb, folder, drive,
                last_modified, indexed_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                filename, filepath, ext,
                round(size, 2), folder, drive,
                modified,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M"
                )
            ))
            conn.commit()
            conn.close()
            logger.debug(
                f"New file indexed: {filename}"
            )
        except Exception as e:
            logger.debug(f"Watcher index error: {e}")
    
    def on_deleted(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        
        try:
            conn = sqlite3.connect(
                self.indexer.db_path
            )
            conn.execute("""
                DELETE FROM file_index
                WHERE filepath = ?
            """, (filepath,))
            conn.commit()
            conn.close()
            logger.debug(
                f"File removed from index: "
                f"{os.path.basename(filepath)}"
            )
        except Exception as e:
            logger.debug(f"Watcher delete error: {e}")
    
    def on_moved(self, event):
        if event.is_directory:
            return
        
        old_path = event.src_path
        new_path = event.dest_path
        new_name = os.path.basename(new_path)
        
        try:
            conn = sqlite3.connect(
                self.indexer.db_path
            )
            conn.execute("""
                UPDATE file_index
                SET filepath = ?,
                    filename = ?,
                    folder = ?
                WHERE filepath = ?
            """, (
                new_path,
                new_name,
                os.path.dirname(new_path),
                old_path
            ))
            conn.commit()
            conn.close()
            logger.debug(
                f"File moved: {new_name}"
            )
        except Exception as e:
            logger.debug(f"Watcher move error: {e}")

class FileIndexer:
    def __init__(self, db_path="opendesk.db"):
        self.db_path = db_path
        self.is_indexing = False
        self._setup_db()
    
    def _setup_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS 
            file_index (
                id INTEGER PRIMARY KEY,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL UNIQUE,
                extension TEXT,
                size_kb REAL,
                folder TEXT,
                drive TEXT,
                last_modified TEXT,
                indexed_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS
            known_paths (
                id INTEGER PRIMARY KEY,
                path_type TEXT,
                path TEXT UNIQUE,
                display_name TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS "
            "idx_filename ON file_index(filename)"
        )
        conn.commit()
        conn.close()
    
    def discover_all_paths(self):
        from opendesk.utils.path_detector import UniversalPathDetector
        
        paths = UniversalPathDetector.get_all_user_folders()
        
        # Save all discovered paths to DB
        conn = sqlite3.connect(self.db_path)
        for name, path in paths.items():
            try:
                # Use a nice display name
                display_name = name.replace("_", " ").title()
                conn.execute("""
                    INSERT OR REPLACE INTO 
                    known_paths 
                    (path_type, path, display_name)
                    VALUES (?, ?, ?)
                """, (name, path, display_name))
                logger.debug(f"Discovered path: {display_name} -> {path}")
            except Exception as e:
                logger.debug(f"DB insert: {e}")
        conn.commit()
        conn.close()
        
        return paths
    
    def index_files(self, paths: dict):
        self.is_indexing = True
        total = 0
        
        # Priority folders index deeply (using lowercase keys from UniversalPathDetector)
        priority_folders = [
            "documents", "downloads",
            "desktop", "pictures",
            "music", "videos",
        ]
        
        conn = sqlite3.connect(self.db_path)
        
        for name, base_path in paths.items():
            if not os.path.exists(base_path):
                continue
            
            # Deep scan for priority folders and all onedrive folders
            # Shallow scan for drives
            is_priority = name in priority_folders or name.startswith("onedrive")
            max_depth = 5 if is_priority else 2
            
            logger.debug(
                f"Indexing {name}: {base_path}"
            )
            
            try:
                for root, dirs, files in \
                        os.walk(base_path):
                    
                    # Check depth
                    depth = root[
                        len(base_path):
                    ].count(os.sep)
                    
                    if depth > max_depth:
                        dirs.clear()
                        continue
                    
                    # Skip system folders
                    dirs[:] = [
                        d for d in dirs
                        if d not in [
                            'node_modules',
                            '__pycache__',
                            '.git',
                            'Windows',
                            'System32',
                            '$Recycle.Bin',
                            'AppData',
                            '.venv',
                        ]
                    ]
                    
                    for filename in files:
                        filepath = os.path.join(
                            root, filename
                        )
                        try:
                            ext = os.path.splitext(
                                filename
                            )[1].lower()
                            size = os.path.getsize(
                                filepath
                            ) / 1024
                            modified = datetime\
                                .fromtimestamp(
                                    os.path.getmtime(
                                        filepath
                                    )
                                ).strftime(
                                    "%Y-%m-%d %H:%M"
                                )
                            
                            drive = filepath[:3]
                            folder = os.path.dirname(
                                filepath
                            )
                            
                            conn.execute("""
                                INSERT OR REPLACE 
                                INTO file_index
                                (filename, filepath,
                                extension, size_kb,
                                folder, drive,
                                last_modified,
                                indexed_at)
                                VALUES 
                                (?,?,?,?,?,?,?,?)
                            """, (
                                filename,
                                filepath,
                                ext,
                                round(size, 2),
                                folder,
                                drive,
                                modified,
                                datetime.now()
                                    .strftime(
                                        "%Y-%m-%d %H:%M"
                                    )
                            ))
                            total += 1
                            
                            if total % 100 == 0:
                                conn.commit()
                                logger.debug(
                                    f"Indexed {total}"
                                    f" files..."
                                )
                                
                        except Exception as e:
                            logger.debug(f"Failed to index file mapping: {e}")
                            continue
                            
            except PermissionError:
                logger.debug(
                    f"No permission: {base_path}"
                )
                continue
        
        conn.commit()
        conn.close()
        self.is_indexing = False
        logger.debug(
            f"Indexing complete! "
            f"Total files: {total}"
        )
        return total
    
    def find_file(self, filename: str) -> list:
        conn = sqlite3.connect(self.db_path)
        
        # Exact match first
        results = conn.execute("""
            SELECT filepath, folder, size_kb
            FROM file_index
            WHERE LOWER(filename) = LOWER(?)
            ORDER BY last_modified DESC
        """, (filename,)).fetchall()
        
        # Fuzzy match if no exact
        if not results:
            results = conn.execute("""
                SELECT filepath, folder, size_kb
                FROM file_index
                WHERE LOWER(filename) 
                LIKE LOWER(?)
                ORDER BY last_modified DESC
                LIMIT 5
            """, (f"%{filename}%",)).fetchall()
        
        conn.close()
        return results
    
    def get_all_known_paths(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT path_type, path, display_name
            FROM known_paths
        """).fetchall()
        conn.close()
        return {
            row[0]: {
                "path": row[1],
                "name": row[2]
            }
            for row in rows
        }
    
    def start_realtime_watcher(self, paths: dict):
        event_handler = OpenDeskFileWatcher(self)
        observer = Observer()
        
        # Watch priority folders only
        # Not entire drives (too heavy)
        priority_watch = [
            "documents", "downloads",
            "desktop", "pictures",
            "music", "videos",
        ]
        
        watched_count = 0
        for name, info in paths.items():
            if name in priority_watch or name.startswith("onedrive"):
                path = info if isinstance(
                    info, str
                ) else info.get("path", "")
                
                if os.path.exists(path):
                    observer.schedule(
                        event_handler,
                        path,
                        recursive=True
                    )
                    watched_count += 1
                    logger.debug(
                        f"Watching: {path}"
                    )
        
        observer.start()
        logger.debug(
            f"Real time watcher active on "
            f"{watched_count} folders"
        )
        return observer

    def stop_watcher(self):
        if hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()
            logger.debug("File watcher stopped")

    def start_background_indexing(self):
        def _run():
            try:
                logger.debug(
                    "Discovering all paths..."
                )
                paths = self.discover_all_paths()
                
                logger.debug(
                    f"Indexing {len(paths)} locations"
                )
                total = self.index_files(paths)
                
                logger.debug(
                    f"Indexed {total} files! "
                    f"Starting real time watcher..."
                )
                
                # Start watchdog AFTER
                # initial index complete
                self.observer = (
                    self.start_realtime_watcher(paths)
                )
                
            except Exception as e:
                logger.error(f"Indexer error: {e}")
        
        thread = threading.Thread(
            target=_run,
            daemon=True,
            name="FileIndexer"
        )
        thread.start()

# Global instance
file_indexer = FileIndexer()
