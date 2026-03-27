import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from opendesk.agent import run_agent_loop

async def status_updater(status: str):
    print(f"[{status}]", end="\r")

async def main():
    print("====================================")
    print("    OpenDeskAI Terminal CLI mode")
    print("    Type 'exit' or 'quit' to close")
    print("====================================")
    
    history = []
    
    while True:
        try:
            text = input("\n> You: ")
            if text.lower() in ["exit", "quit"]:
                break
                
            if not text.strip():
                continue
                
            print("[Agent thinking...]")
            response, new_history, attachments = await run_agent_loop(
                user_text=text, 
                history=history, 
                status_callback=status_updater
            )
            
            history = new_history[-10:] # Keep last 10 messages context
            
            print(f"\n> Bot: {response}")
            if attachments:
                print(f"> 📎 Attachments saved: {attachments}")
                
        except (KeyboardInterrupt, EOFError):
             break
        except Exception as e:
             print(f"\nError: {e}")

if __name__ == "__main__":
    asyncio.run(main())
