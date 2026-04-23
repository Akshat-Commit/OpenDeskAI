class SimpleMemory:
    def __init__(self):
        self.history = {}
    
    def get_context(self, chat_id, limit=20):
        msgs = self.history.get(chat_id, [])
        return msgs[-limit:]
    
    def add(self, chat_id, role, content):
        if chat_id not in self.history:
            self.history[chat_id] = []
            
        # Protect LLM Context Windows (Truncate super long text from previous interactions)
        if isinstance(content, str) and len(content) > 1500:
            content = content[:1500] + "\n...[Content truncated to save AI memory]"
            
        self.history[chat_id].append({
            "role": role,
            "content": content
        })
        
        # Keep only last 15 messages (increased from 10 to preserve file attachment context longer)
        self.history[chat_id] = self.history[chat_id][-15:]

# Global memory instance
simple_memory = SimpleMemory()
