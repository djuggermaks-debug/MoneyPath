import os
import requests

api_key = os.environ["TWELVE_DATA_KEY"]

resp = requests.get(
    "https://api.twelvedata.com/symbol_search",
    params={"symbol": "brent", "apikey": api_key},
    timeout=10,
)
print(resp.json())
