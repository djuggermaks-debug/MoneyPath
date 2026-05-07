import yfinance as yf
import pandas as pd


SYMBOLS = {
    "OIL":  "BZ=F",
    "GAS":  "NG=F",
    "GOLD": "GC=F",
    "BTC":  "BTC-USD",
}


def get_market_data(instrument_key):
    symbol = SYMBOLS.get(instrument_key, "BZ=F")

    ticker = yf.Ticker(symbol)
    df = ticker.history(period="5d", interval="15m")

    if df.empty:
        print(f"yfinance: нет данных для {symbol}")
        return {"price": {}, "indicators": {}, "position": None}

    current = df.iloc[-1]
    prev_close = df.iloc[-2]["Close"] if len(df) > 1 else current["Close"]
    change_pct = round((current["Close"] - prev_close) / prev_close * 100, 2)

    price = {
        "symbol": symbol,
        "mid": round(float(current["Close"]), 3),
        "change_pct": change_pct,
    }

    indicators = _calculate_indicators(df)

    print(f"yfinance цена: {price}")
    print(f"yfinance индикаторы: {indicators}")

    return {
        "price": price,
        "indicators": indicators,
        "position": None,
    }


def _calculate_indicators(df):
    closes = df["Close"].dropna().tolist()
    highs  = df["High"].dropna().tolist()
    lows   = df["Low"].dropna().tolist()

    if len(closes) < 14:
        return {}

    rsi = _rsi(closes, 14)
    support, resistance = _support_resistance(highs, lows)
    pivot = _pivot_points(df)

    return {
        "rsi": round(rsi, 1),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "pivot": round(pivot, 2),
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


def _support_resistance(highs, lows, lookback=50):
    recent_highs = highs[-lookback:]
    recent_lows  = lows[-lookback:]

    resistance = max(recent_highs)
    support    = min(recent_lows)

    return support, resistance


def _pivot_points(df):
    # Берём вчерашнюю дневную свечу для расчёта пивота
    daily = df["Close"].resample("1D").ohlc().dropna()
    if len(daily) < 2:
        return 0.0
    yesterday = daily.iloc[-2]
    pivot = (yesterday["high"] + yesterday["low"] + yesterday["close"]) / 3
    return float(pivot)
