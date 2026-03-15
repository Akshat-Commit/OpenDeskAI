import requests

payload = {
    "model": "minimax-m2:cloud",
    "prompt": "Hello",
    "stream": False
}

try:
    print("Sending request to minimax-m2:cloud...")
    resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=10)
    print(f"Status: {resp.status_code}")
    print(resp.text)
except Exception as e:
    print(f"Error: {e}")
