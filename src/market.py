import requests
import csv
import io
from datetime import datetime, timezone


SYMBOLS = {
    "OIL":  "cb.f",    # Brent crude (Stooq)
    "GAS":  "ng.f",    # Natural Gas
    "GOLD": "gc.f",    # Gold
    "BTC":  "btc.v",   # Bitcoin
}

STOOQ_URL = "https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
STOOQ_HIST = "https://stooq.com/q/d/l/?s={symbol}&i=15"  # 15-min history


def get_market_data(instrument_key):
    symbol = SYMBOLS.get(instrument_key, "cb.f")

    price = _get_price(symbol)
    candles = _get_candles(symbol)
    indicators = _calculate_indicators(candles)

    print(f"Stooq цена: {price}")
    print(f"Stooq свечей: {len(candles)}")

    return {
        "price": price,
        "indicators": indicators,
        "position": None,
    }


def _get_price(symbol):
    resp = requests.get(STOOQ_URL.format(symbol=symbol), timeout=10)
    reader = csv.DictReader(io.StringIO(resp.text))
    row = next(reader, {})

    close = row.get("Close", "N/D")
    if close == "N/D" or not close:
        return {"symbol": symbol, "mid": None, "change_pct": None}

    open_price = float(row.get("Open", close))
    close_price = float(close)
    change_pct = round((close_price - open_price) / open_price * 100, 2) if open_price else 0

    return {
        "symbol": symbol,
        "mid": round(close_price, 3),
        "change_pct": change_pct,
    }


def _get_candles(symbol):
    resp = requests.get(STOOQ_HIST.format(symbol=symbol), timeout=10)
    reader = csv.DictReader(io.StringIO(resp.text))
    candles = []
    for row in reader:
        try:
            candles.append({
                "open":  float(row["Open"]),
                "high":  float(row["High"]),
                "low":   float(row["Low"]),
                "close": float(row["Close"]),
            })
        except (ValueError, KeyError):
            continue
    return candles


def _calculate_indicators(candles):
    if len(candles) < 14:
        return {}

    closes = [c["close"] for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]

    rsi        = _rsi(closes, 14)
    support    = min(lows[-50:])
    resistance = max(highs[-50:])
    pivot      = _pivot(candles)

    return {
        "rsi":        round(rsi, 1),
        "support":    round(support, 2),
        "resistance": round(resistance, 2),
        "pivot":      round(pivot, 2),
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


def _pivot(candles):
    if len(candles) < 2:
        return 0.0
    prev = candles[-2]
    return (prev["high"] + prev["low"] + prev["close"]) / 3
