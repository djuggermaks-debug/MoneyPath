import requests

# Brent crude на Stooq
# co.f = Brent crude futures
urls = {
    "Brent (co.f)":    "https://stooq.com/q/l/?s=co.f&f=sd2t2ohlcv&h&e=csv",
    "Brent (brent.uk)": "https://stooq.com/q/l/?s=brent.uk&f=sd2t2ohlcv&h&e=csv",
    "WTI (cl.f)":      "https://stooq.com/q/l/?s=cl.f&f=sd2t2ohlcv&h&e=csv",
}

for name, url in urls.items():
    resp = requests.get(url, timeout=10)
    print(f"\n--- {name} ---")
    print(resp.text[:300])
