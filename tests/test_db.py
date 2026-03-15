import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opendesk.db.connection import db
from opendesk.db import crud

def test_database():
    print("Testing Database connection and schema initialization...")
    # This will initialize the schema if not already initialized
    cursor = db.get_cursor()
    print("✓ Successfully connected to DB and initialized schema.")
    
    print("\nTesting log_command...")
    cmd_id = crud.log_command("open_app(Spotify)", "success", "Opened Spotify successfully")
    print(f"✓ Logged command with ID: {cmd_id}")
    
    print("\nTesting user settings...")
    crud.set_setting("theme", "dark")
    theme = crud.get_setting("theme")
    print(f"✓ Set and retrieved setting theme={theme}")
    
    print("\nTesting chat history...")
    crud.log_chat_message("user", "Hello bot!")
    crud.log_chat_message("assistant", "Hello human!")
    history = crud.get_recent_chat_history(2)
    print(f"✓ Retrieved history: {history}")
    
    print("\nTesting app usage...")
    usage_id = crud.log_app_start("VS Code")
    import time
    time.sleep(1) # simulate usage
    crud.log_app_end(usage_id)
    print(f"✓ Logged app usage session for ID {usage_id}")
    
    print("\nAll database tests passed successfully!")

if __name__ == "__main__":
    test_database()
