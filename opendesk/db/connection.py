import sqlite3
import os
from loguru import logger
from opendesk.config import DATABASE_PATH



class DatabaseConnection:
    _instance = None
    connection: sqlite3.Connection | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._instance.connection = None
        return cls._instance

    def connect(self):
        if self.connection is None:
            try:
                # Ensure the directory exists if the path contains one
                db_dir = os.path.dirname(DATABASE_PATH)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                
                self.connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
                self.connection.row_factory = sqlite3.Row  # To return dict-like rows
                logger.debug(f"Connected to SQLite database at {DATABASE_PATH}")
                self._initialize_schema()
            except sqlite3.Error as e:
                logger.error(f"Error connecting to database: {e}")
                raise

        return self.connection

    def _initialize_schema(self):
        assert self.connection is not None
        try:
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            if os.path.exists(schema_path):
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_script = f.read()
                
                cursor = self.connection.cursor()
                cursor.executescript(schema_script)
                self.connection.commit()
                logger.debug("Database schema initialized successfully.")
            else:
                logger.debug(f"Schema file not found at {schema_path}. Skipping initialization.")
        except sqlite3.Error as e:
            logger.error(f"Error initializing schema: {e}")
            raise

    def get_cursor(self):
        if self.connection is None:
            self.connect()
        assert self.connection is not None
        return self.connection.cursor()

    def commit(self):
        if self.connection:
            self.connection.commit()

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed.")

# Singleton instance for easy import
db = DatabaseConnection()
