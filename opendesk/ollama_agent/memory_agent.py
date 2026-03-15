import sqlite3
import json
from loguru import logger
from datetime import datetime
from opendesk.config import DATABASE_PATH



class MemoryAgent:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self._init_db()

    def _init_db(self):
        """Initialize the agent_memory table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_pattern TEXT UNIQUE,
                successful_tool TEXT,
                successful_model TEXT,
                failed_approaches TEXT, -- JSON list
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def get_context(self, command: str):
        """
        Check if a similar command has worked before.
        Returns a dictionary with successful patterns if found.
        """
        # Simple keyword-based pattern matching for now
        # We could improve this with embeddings later
        words = command.lower().split()
        potential_patterns = []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT command_pattern, successful_tool, successful_model, failed_approaches FROM agent_memory")
        rows = cursor.fetchall()
        conn.close()

        best_match = None
        for pattern, tool, model, failed in rows:
            # Check if all keywords in pattern are in command
            pattern_parts = pattern.lower().split()
            if all(part in command.lower() for part in pattern_parts):
                best_match = {
                    "pattern": pattern,
                    "tool": tool,
                    "model": model,
                    "failed": json.loads(failed) if failed else []
                }
                break
        
        return best_match

    def record_result(self, command: str, tool: str, model: str, success: bool):
        """Record the outcome of a command execution."""
        # For memory, we use simplified patterns (e.g., "play spotify")
        # For now, let's just use the command text or extract core intent
        pattern = command.lower().strip()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT success_count, fail_count, failed_approaches FROM agent_memory WHERE command_pattern = ?", (pattern,))
            row = cursor.fetchone()
            
            if row:
                s_count, f_count, failed_json = row
                failed_list = json.loads(failed_json) if failed_json else []
                
                if success:
                    cursor.execute("""
                        UPDATE agent_memory 
                        SET success_count = ?, successful_tool = ?, successful_model = ?, last_updated = ?
                        WHERE command_pattern = ?
                    """, (s_count + 1, tool, model, datetime.now(), pattern))
                else:
                    if tool and tool not in failed_list:
                        failed_list.append(tool)
                    cursor.execute("""
                        UPDATE agent_memory 
                        SET fail_count = ?, failed_approaches = ?, last_updated = ?
                        WHERE command_pattern = ?
                    """, (f_count + 1, json.dumps(failed_list), datetime.now(), pattern))
            else:
                if success:
                    cursor.execute("""
                        INSERT INTO agent_memory (command_pattern, successful_tool, successful_model, success_count, last_updated)
                        VALUES (?, ?, ?, ?, ?)
                    """, (pattern, tool, model, 1, datetime.now()))
                else:
                    cursor.execute("""
                        INSERT INTO agent_memory (command_pattern, failed_approaches, fail_count, last_updated)
                        VALUES (?, ?, ?, ?)
                    """, (pattern, json.dumps([tool] if tool else []), 1, datetime.now()))
            
            conn.commit()
        except Exception as e:
            logger.error(f"Memory recording failed: {e}")
        finally:
            conn.close()

memory_agent = MemoryAgent()
