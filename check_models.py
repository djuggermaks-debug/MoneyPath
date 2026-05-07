import os
import requests

api_key = os.environ["GEMINI_API_KEY"]
resp = requests.get(
    f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
    timeout=10,
)
resp.raise_for_status()
models = resp.json().get("models", [])
for m in models:
    name = m.get("name", "")
    methods = m.get("supportedGenerationMethods", [])
    if "generateContent" in methods:
        print(name)
