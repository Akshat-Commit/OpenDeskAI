import sys
sys.path.append(r"c:\Users\AKSHAT JAIN\OneDrive\Desktop\OpenDeskAI")
from opendesk.ollama_agent.langchain_agent import run

print("Testing 4-Layer Architecture - Fallback to Vision (Layer 4)")
print("-" * 50)
print("Query: 'Turn off my bluetooth'")

# Mock history to test the fresh vision loop execution
response, attachments = run("Turn off my bluetooth")

print("\n--- FINAL AGENT OUTPUT ---")
print(response)
print("\n--- ATTACHMENTS ---")
print(attachments)
