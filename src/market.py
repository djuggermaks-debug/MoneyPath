import os
import requests
import csv
import io

SYMBOLS = {
    "OIL":  "cb.f",
    "GAS":  "ng.f",
    "GOLD": "gc.f",
    "BTC":  "btc.v",
}

TV_SYMBOLS = {
    "OIL":  ("UKOIL",  "OANDA"),
    "GAS":  ("NGAS",   "OANDA"),
    "GOLD": ("XAUUSD", "OANDA"),
    "BTC":  ("BTCUSD", "BINANCE"),
}

STOOQ_URL = "https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"


def get_market_data(instrument_key):
    candles_d, candles_4h = _get_candles_tv(instrument_key)
    price      = _price_from_candles(candles_d, instrument_key)
    indicators = _calculate_indicators(candles_d, candles_4h)

    print(f"TradingView цена: {price}")
    print(f"Свечей дневных: {len(candles_d)} | 4H: {len(candles_4h)}")
    if indicators.get("tech_bias"):
        print(f"Технический перевес: {indicators['tech_bias']} (score {indicators.get('tech_score', 0):+d})")

    return {
        "price":      price,
        "indicators": indicators,
        "position":   None,
    }


def _price_from_candles(candles_d, instrument_key):
    if candles_d:
        last = candles_d[-1]
        prev = candles_d[-2] if len(candles_d) > 1 else last
        close = last["close"]
        change_pct = round((last["close"] - prev["close"]) / prev["close"] * 100, 2) if prev["close"] else 0
        return {"symbol": instrument_key, "mid": round(close, 3), "change_pct": change_pct}
    # Запасной вариант если TradingView недоступен
    symbol = SYMBOLS.get(instrument_key, "cb.f")
    return _get_stooq_price(symbol)


def _get_stooq_price(symbol):
    resp = requests.get(STOOQ_URL.format(symbol=symbol), timeout=10)
    reader = csv.DictReader(io.StringIO(resp.text))
    row = next(reader, {})

    close = row.get("Close", "N/D")
    if close == "N/D" or not close:
        return {"symbol": symbol, "mid": None, "change_pct": None}

    open_price  = float(row.get("Open", close))
    close_price = float(close)
    change_pct  = round((close_price - open_price) / open_price * 100, 2) if open_price else 0

    return {
        "symbol":     symbol,
        "mid":        round(close_price, 3),
        "change_pct": change_pct,
    }


def _get_candles_tv(instrument_key):
    try:
        from src.tvdatafeed import TvDatafeed, Interval
        tv_symbol, exchange = TV_SYMBOLS.get(instrument_key, ("UKOIL", "OANDA"))
        tv_token = os.environ.get("TV_SESSION")
        tv = TvDatafeed(token=tv_token)
        df_d  = tv.get_hist(symbol=tv_symbol, exchange=exchange, interval=Interval.in_daily,  n_bars=100)
        df_4h = tv.get_hist(symbol=tv_symbol, exchange=exchange, interval=Interval.in_4_hour, n_bars=60)
        return _parse_df(df_d), _parse_df(df_4h)
    except Exception as e:
        print(f"tvDatafeed ошибка: {e}")
        return [], []


def _parse_df(df):
    if df is None or df.empty:
        return []
    candles = []
    for _, row in df.iterrows():
        candles.append({
            "open":  float(row["open"]),
            "high":  float(row["high"]),
            "low":   float(row["low"]),
            "close": float(row["close"]),
        })
    return candles


# ── Математические утилиты ────────────────────────────────────────────────────

def _ema_series(values, period):
    """Возвращает серию EMA той же длины (первые period-1 позиций = None)."""
    if len(values) < period:
        return [None] * len(values)
    k = 2 / (period + 1)
    result = [None] * (period - 1)
    sma = sum(values[:period]) / period
    result.append(sma)
    for v in values[period:]:
        result.append(result[-1] * (1 - k) + v * k)
    return result


def _ema_last(values, period):
    """Последнее значение EMA."""
    series = _ema_series(values, period)
    valid = [v for v in series if v is not None]
    return valid[-1] if valid else None


def _rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
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


def _std(values):
    n = len(values)
    if n < 2:
        return 0
    mean = sum(values) / n
    return (sum((x - mean) ** 2 for x in values) / n) ** 0.5


def _pivot(candles):
    if len(candles) < 2:
        return 0.0
    prev = candles[-2]
    return (prev["high"] + prev["low"] + prev["close"]) / 3


# ── Основной расчёт индикаторов ───────────────────────────────────────────────

def _calculate_indicators(candles_d, candles_4h):
    result = {}

    if len(candles_d) >= 20:
        closes = [c["close"] for c in candles_d]
        highs  = [c["high"]  for c in candles_d]
        lows   = [c["low"]   for c in candles_d]

        # RSI
        rsi = _rsi(closes, 14)
        if rsi is not None:
            result["rsi"] = round(rsi, 1)

        # Поддержка / сопротивление
        result["support"]    = round(min(lows[-20:]), 2)
        result["resistance"] = round(max(highs[-20:]), 2)
        result["pivot"]      = round(_pivot(candles_d), 2)

        # EMA 20 / 50
        ema20 = _ema_last(closes, 20)
        ema50 = _ema_last(closes, 50) if len(closes) >= 50 else None
        if ema20 is not None:
            result["ema20"] = round(ema20, 2)
        if ema50 is not None:
            result["ema50"] = round(ema50, 2)

        # Тренд по EMA
        price = closes[-1]
        if ema20 and ema50:
            if price > ema20 > ema50:
                result["ema_trend"] = "восходящий (цена > EMA20 > EMA50)"
            elif price < ema20 < ema50:
                result["ema_trend"] = "нисходящий (цена < EMA20 < EMA50)"
            elif price > ema20 and ema20 < ema50:
                result["ema_trend"] = "возможный разворот вверх (цена пробила EMA20 снизу)"
            elif price < ema20 and ema20 > ema50:
                result["ema_trend"] = "возможный разворот вниз (цена пробила EMA20 сверху)"
            else:
                result["ema_trend"] = "боковик"

        # MACD (12, 26, 9)
        if len(closes) >= 35:
            ema12_s = _ema_series(closes, 12)
            ema26_s = _ema_series(closes, 26)
            macd_vals = []
            for e12, e26 in zip(ema12_s, ema26_s):
                if e12 is not None and e26 is not None:
                    macd_vals.append(e12 - e26)
            if len(macd_vals) >= 9:
                signal_s = _ema_series(macd_vals, 9)
                valid_sig = [v for v in signal_s if v is not None]
                if valid_sig:
                    macd_line   = macd_vals[-1]
                    signal_line = valid_sig[-1]
                    histogram   = macd_line - signal_line
                    result["macd_line"]   = round(macd_line, 4)
                    result["macd_signal"] = round(signal_line, 4)
                    result["macd_hist"]   = round(histogram, 4)
                    result["macd_bias"]   = "бычий" if macd_line > signal_line else "медвежий"

        # Bollinger Bands (20, 2)
        if len(closes) >= 20:
            sma20   = sum(closes[-20:]) / 20
            std20   = _std(closes[-20:])
            bb_up   = sma20 + 2 * std20
            bb_low  = sma20 - 2 * std20
            bb_rng  = bb_up - bb_low
            bb_pct  = (price - bb_low) / bb_rng if bb_rng > 0 else 0.5
            result["bb_upper"]  = round(bb_up, 2)
            result["bb_middle"] = round(sma20, 2)
            result["bb_lower"]  = round(bb_low, 2)
            result["bb_pct"]    = round(bb_pct, 3)
            if bb_pct > 0.85:
                result["bb_position"] = "у верхней полосы (перекупленность)"
            elif bb_pct < 0.15:
                result["bb_position"] = "у нижней полосы (перепроданность)"
            elif bb_pct > 0.6:
                result["bb_position"] = "в верхней зоне"
            elif bb_pct < 0.4:
                result["bb_position"] = "в нижней зоне"
            else:
                result["bb_position"] = "в середине канала"

        # Паттерн последних свечей
        result["pattern"] = _detect_pattern(candles_d)

    # 4H индикаторы
    if len(candles_4h) >= 20:
        closes_4h = [c["close"] for c in candles_4h]
        rsi_4h = _rsi(closes_4h, 14)
        ema20_4h = _ema_last(closes_4h, 20)
        if rsi_4h is not None:
            result["rsi_4h"] = round(rsi_4h, 1)
        if ema20_4h is not None:
            result["ema20_4h"] = round(ema20_4h, 2)
        price_4h = closes_4h[-1]
        if ema20_4h:
            result["trend_4h"] = "выше EMA20 (бычий)" if price_4h > ema20_4h else "ниже EMA20 (медвежий)"

    # Технический скор и перевес
    score, bias, signals = _tech_score(result, candles_d)
    result["tech_score"]   = score
    result["tech_bias"]    = bias
    result["tech_signals"] = signals

    return result


def _detect_pattern(candles):
    if len(candles) < 3:
        return "недостаточно данных"

    c1, c2, c3 = candles[-3], candles[-2], candles[-1]

    def body(c):      return abs(c["close"] - c["open"])
    def rng(c):       return c["high"] - c["low"]
    def is_bull(c):   return c["close"] > c["open"]
    def is_bear(c):   return c["close"] < c["open"]
    def upper_sh(c):  return c["high"] - max(c["open"], c["close"])
    def lower_sh(c):  return min(c["open"], c["close"]) - c["low"]

    b3, r3 = body(c3), rng(c3)

    # Доджи
    if r3 > 0 and b3 / r3 < 0.08:
        return "Доджи — рынок в нерешительности, возможен разворот"

    # Молот (бычий)
    if (r3 > 0 and lower_sh(c3) > 2 * b3
            and upper_sh(c3) < b3 * 0.5
            and b3 / r3 < 0.35):
        return "Молот — сигнал бычьего разворота"

    # Перевёрнутый молот / падающая звезда (медвежий)
    if (r3 > 0 and upper_sh(c3) > 2 * b3
            and lower_sh(c3) < b3 * 0.5
            and b3 / r3 < 0.35):
        return "Падающая звезда — сигнал медвежьего разворота"

    # Бычье поглощение
    if (is_bear(c2) and is_bull(c3)
            and c3["open"] <= c2["close"]
            and c3["close"] >= c2["open"]):
        return "Бычье поглощение — сильный сигнал разворота вверх"

    # Медвежье поглощение
    if (is_bull(c2) and is_bear(c3)
            and c3["open"] >= c2["close"]
            and c3["close"] <= c2["open"]):
        return "Медвежье поглощение — сильный сигнал разворота вниз"

    # Утренняя звезда (3 свечи, бычий разворот)
    if (is_bear(c1) and body(c2) < body(c1) * 0.4
            and is_bull(c3) and c3["close"] > (c1["open"] + c1["close"]) / 2):
        return "Утренняя звезда — трёхсвечной бычий разворот"

    # Вечерняя звезда (3 свечи, медвежий разворот)
    if (is_bull(c1) and body(c2) < body(c1) * 0.4
            and is_bear(c3) and c3["close"] < (c1["open"] + c1["close"]) / 2):
        return "Вечерняя звезда — трёхсвечной медвежий разворот"

    # Три белых солдата
    if is_bull(c1) and is_bull(c2) and is_bull(c3):
        if c2["close"] > c1["close"] and c3["close"] > c2["close"]:
            return "Три белых солдата — устойчивый бычий импульс"

    # Три чёрных вороны
    if is_bear(c1) and is_bear(c2) and is_bear(c3):
        if c2["close"] < c1["close"] and c3["close"] < c2["close"]:
            return "Три чёрных вороны — устойчивый медвежий импульс"

    return "Бычья свеча" if is_bull(c3) else "Медвежья свеча"


def _tech_score(ind, candles_d):
    """Считает технический скор [-6..+6] и определяет перевес."""
    score   = 0
    signals = []

    price = candles_d[-1]["close"] if candles_d else None

    # 1. EMA тренд (+/-2)
    ema20 = ind.get("ema20")
    ema50 = ind.get("ema50")
    if price and ema20 and ema50:
        if price > ema20 > ema50:
            score += 2
            signals.append(f"Цена ({price:.2f}) > EMA20 ({ema20}) > EMA50 ({ema50}) — восходящий тренд")
        elif price < ema20 < ema50:
            score -= 2
            signals.append(f"Цена ({price:.2f}) < EMA20 ({ema20}) < EMA50 ({ema50}) — нисходящий тренд")
        elif price > ema20:
            score += 1
            signals.append(f"Цена выше EMA20 ({ema20})")
        elif price < ema20:
            score -= 1
            signals.append(f"Цена ниже EMA20 ({ema20})")

    # 2. RSI (+/-1)
    rsi = ind.get("rsi")
    if rsi is not None:
        if rsi < 35:
            score += 1
            signals.append(f"RSI {rsi} — зона перепроданности (бычий)")
        elif rsi > 65:
            score -= 1
            signals.append(f"RSI {rsi} — зона перекупленности (медвежий)")

    # 3. MACD (+/-1)
    macd_l = ind.get("macd_line")
    macd_s = ind.get("macd_signal")
    if macd_l is not None and macd_s is not None:
        if macd_l > macd_s:
            score += 1
            signals.append(f"MACD ({macd_l:.4f}) > сигнал ({macd_s:.4f}) — бычий импульс")
        else:
            score -= 1
            signals.append(f"MACD ({macd_l:.4f}) < сигнал ({macd_s:.4f}) — медвежий импульс")

    # 4. Bollinger Bands (+/-1)
    bb_pct = ind.get("bb_pct")
    if bb_pct is not None:
        if bb_pct < 0.15:
            score += 1
            signals.append(f"Цена у нижней полосы Боллинджера (BB%={bb_pct:.2f}) — перепроданность")
        elif bb_pct > 0.85:
            score -= 1
            signals.append(f"Цена у верхней полосы Боллинджера (BB%={bb_pct:.2f}) — перекупленность")

    # 5. 4H RSI (+/-1)
    rsi_4h = ind.get("rsi_4h")
    if rsi_4h is not None:
        if rsi_4h < 40:
            score += 1
            signals.append(f"RSI 4H = {rsi_4h} — перепроданность на младшем ТФ")
        elif rsi_4h > 60:
            score -= 1
            signals.append(f"RSI 4H = {rsi_4h} — перекупленность на младшем ТФ")

    # Перевес
    if score >= 4:
        bias = "сильный бычий"
    elif score >= 2:
        bias = "бычий"
    elif score >= 1:
        bias = "слабо бычий"
    elif score <= -4:
        bias = "сильный медвежий"
    elif score <= -2:
        bias = "медвежий"
    elif score <= -1:
        bias = "слабо медвежий"
    else:
        bias = "нейтральный"

    return score, bias, signals
