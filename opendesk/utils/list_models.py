import requests

try:
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    models = response.json().get("models", [])
    print("AVAILABLE MODELS:")
    for m in models:
        print(f"- {m['name']}")
except Exception as e:
    print(f"Error: {e}")
