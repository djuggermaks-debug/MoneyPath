import requests

# Brent crude на Stooq
# co.f = Brent crude futures
urls = {
    "Brent (co.f)":    "https://stooq.com/q/l/?s=co.f&f=sd2t2ohlcv&h&e=csv",
    "Brent (lco.f)":   "https://stooq.com/q/l/?s=lco.f&f=sd2t2ohlcv&h&e=csv",
    "Brent (bco.f)":   "https://stooq.com/q/l/?s=bco.f&f=sd2t2ohlcv&h&e=csv",
    "Brent (brn.f)":   "https://stooq.com/q/l/?s=brn.f&f=sd2t2ohlcv&h&e=csv",
    "Brent (cb.f)":    "https://stooq.com/q/l/?s=cb.f&f=sd2t2ohlcv&h&e=csv",
    "WTI (cl.f)":      "https://stooq.com/q/l/?s=cl.f&f=sd2t2ohlcv&h&e=csv",
}

for name, url in urls.items():
    resp = requests.get(url, timeout=10)
    print(f"\n--- {name} ---")
    print(resp.text[:300])
