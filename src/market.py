import os
import requests


BASE_URL = "https://api.twelvedata.com"

# Символы для Twelve Data
SYMBOLS = {
    "OIL":  "UKOIL",
    "GAS":  "XNG/USD",
    "GOLD": "XAU/USD",
    "BTC":  "BTC/USD",
}


def get_market_data(instrument_key):
    api_key = os.environ["TWELVE_DATA_KEY"]
    symbol = SYMBOLS.get(instrument_key, "BRENT")

    price = _get_price(symbol, api_key)
    print(f"Twelve Data цена: {price}")
    candles = _get_candles(symbol, api_key)
    print(f"Twelve Data свечей: {len(candles)}")
    indicators = _calculate_indicators(candles)

    return {
        "price": price,
        "indicators": indicators,
        "position": None,  # позиции добавим позже
    }


def _get_price(symbol, api_key):
    resp = requests.get(
        f"{BASE_URL}/price",
        params={"symbol": symbol, "apikey": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    price = float(data.get("price", 0))

    # Изменение за день
    quote = requests.get(
        f"{BASE_URL}/quote",
        params={"symbol": symbol, "apikey": api_key},
        timeout=10,
    ).json()
    change_pct = round(float(quote.get("percent_change", 0)), 2)

    return {
        "symbol": symbol,
        "mid": round(price, 3),
        "change_pct": change_pct,
    }


def _get_candles(symbol, api_key, interval="30min", count=48):
    resp = requests.get(
        f"{BASE_URL}/time_series",
        params={
            "symbol": symbol,
            "interval": interval,
            "outputsize": count,
            "apikey": api_key,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("values", [])


def _calculate_indicators(candles):
    if len(candles) < 14:
        return {}

    closes = [float(c["close"]) for c in candles]
    closes.reverse()  # Twelve Data отдаёт от новых к старым

    rsi = _rsi(closes, 14)
    support = min(closes[-48:])
    resistance = max(closes[-48:])

    return {
        "rsi": round(rsi, 1),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
    }


def _rsi(closes, period=14):
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))
