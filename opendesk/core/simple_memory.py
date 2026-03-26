class SimpleMemory:
    def __init__(self):
        self.history = {}
    
    def get_context(self, chat_id, limit=20):
        msgs = self.history.get(chat_id, [])
        return msgs[-limit:]
    
    def add(self, chat_id, role, content):
        if chat_id not in self.history:
            self.history[chat_id] = []
            
        self.history[chat_id].append({
            "role": role,
            "content": content
        })
        
        # Keep only last 20 messages to prevent memory overflow
        self.history[chat_id] = self.history[chat_id][-20:]

# Global memory instance
simple_memory = SimpleMemory()
