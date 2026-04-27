-- Database Schema for OpenDeskAI

-- Table to store command execution history
CREATE TABLE IF NOT EXISTS command_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_text TEXT NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT, -- 'success', 'failure', 'pending'
    output TEXT
);

-- Table track known files to avoid redundant processing/indexing
CREATE TABLE IF NOT EXISTS file_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    file_type TEXT,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_hash TEXT
);

-- Record of screenshots captured by the bot
CREATE TABLE IF NOT EXISTS screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    context_description TEXT
);

-- Table to store saved workflows (SOPs)
CREATE TABLE IF NOT EXISTS workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    steps_json TEXT NOT NULL, -- JSON serialized string of steps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_run TIMESTAMP
);

-- Logs application usage
CREATE TABLE IF NOT EXISTS app_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name TEXT NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    duration INTEGER -- stored in seconds, computed on end_time
);

-- Application error logs for debugging
CREATE TABLE IF NOT EXISTS error_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    component TEXT,
    error_message TEXT NOT NULL,
    traceback TEXT
);

-- Persistent Key-Value store for application and user settings
CREATE TABLE IF NOT EXISTS user_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- To give the bot memory across restarts
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- OCR text extracted from screenshots by OCRAnalyzer
CREATE TABLE IF NOT EXISTS screenshot_ocr (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screenshot_path TEXT UNIQUE,
    extracted_text TEXT,
    keywords TEXT,
    captured_at TEXT,
    analyzed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ocr_text ON screenshot_ocr(extracted_text);
