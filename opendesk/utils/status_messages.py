STATUS_MESSAGES = {
    # File operations
    "read_file": "📖 Reading your file...",
    "write_file": "✏️ Saving your file...",
    "share_file": "📤 Finding and preparing file...",
    "find_file_location": "🔍 Searching your laptop...",
    "find_latest_file": "🔍 Finding latest file...",
    "find_and_summarize": "📖 Reading and summarizing...",
    "list_directory": "📁 Looking inside folder...",
    "read_and_summarize": "📖 Reading document...",
    "find_files_by_filter": "🔍 Filtering files by date...",
    
    # System operations
    "take_screenshot": "📸 Capturing your screen...",
    "set_volume": "🔊 Adjusting volume...",
    "mute_volume": "🔇 Muting sound...",
    "unmute_volume": "🔊 Unmuting sound...",
    "get_battery_level": "🔋 Checking battery...",
    "get_system_info": "💻 Getting system info...",
    "get_current_time": "🕐 Checking time...",
    
    # App operations
    "open_application": "🚀 Opening app...",
    "close_application": "❌ Closing app...",
    
    # Browser operations
    "search_web": "🌐 Searching the web...",
    "read_webpage": "🌐 Reading webpage...",
    
    # Media operations
    "play_spotify_music": "🎵 Playing music...",
    "pause_music": "⏸️ Pausing music...",
    "resume_music": "▶️ Resuming music...",
    "next_track": "⏭️ Next song...",
    "previous_track": "⏮️ Previous song...",
    
    # WhatsApp operations
    "send_whatsapp_message": "💬 Opening WhatsApp...",
    "send_whatsapp_file": "📎 Sending file on WhatsApp...",
    
    # Document operations
    "create_word_doc": "📝 Creating Word document...",
    "create_excel_file": "📊 Creating Excel file...",
    "create_powerpoint": "📊 Creating presentation...",
    
    # Terminal
    "run_terminal_command": "⚡ Running command...",
    
    # Clipboard
    "read_clipboard": "📋 Reading clipboard...",
    "write_clipboard": "📋 Writing to clipboard...",
    
    # Default
    "default": "⚙️ Working on it...",
}

COMPLETION_MESSAGES = {
    "read_file": "✅ File read!",
    "write_file": "✅ File saved!",
    "share_file": "✅ File ready to send!",
    "take_screenshot": "✅ Screenshot captured!",
    "set_volume": "✅ Volume adjusted!",
    "open_application": "✅ App opened!",
    "search_web": "✅ Found results!",
    "play_spotify_music": "✅ Playing now!",
    "send_whatsapp_message": "✅ Message sent!",
    "send_whatsapp_file": "✅ File sent!",
    "create_word_doc": "✅ Document created!",
    "default": "✅ Done!",
}

def get_status(tool_name: str) -> str:
    return STATUS_MESSAGES.get(tool_name, STATUS_MESSAGES["default"])

def get_completion(tool_name: str) -> str:
    return COMPLETION_MESSAGES.get(tool_name, COMPLETION_MESSAGES["default"])
