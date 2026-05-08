import os
import json
import requests
import time

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def analyze(instrument_name, news_articles, market_data, history, mode="trading"):
    api_key = os.environ["GEMINI_API_KEY"]

    price = market_data.get("price", {})
    indicators = market_data.get("indicators", {})
    position = market_data.get("position")

    position_text = "Нет открытых позиций."
    if position:
        direction = position.get("direction", "")
        level = position.get("level", "")
        pnl = position.get("upl", "")
        position_text = f"Открыта позиция: {direction} с уровня {level}, текущий P&L: {pnl}"

    news_text = ""
    for i, a in enumerate(news_articles[:8], 1):
        news_text += f"{i}. [{a['source']}] {a['title']}\n   {a['summary']}\n\n"

    history_text = ""
    if history:
        for h in history[-5:]:
            history_text += f"- {h.get('date')}: сигнал {h.get('signal')}, цена изменилась на {h.get('price_change_4h', '?')}\n"

    if mode == "digest":
        prompt = _digest_prompt(news_text)
    else:
        prompt = _trading_prompt(
            instrument_name, price, indicators,
            position_text, news_text, history_text
        )

    resp = None
    for attempt in range(3):
        resp = requests.post(
            f"{GEMINI_URL}?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        if resp.status_code == 429:
            wait = 30 * (attempt + 1)
            print(f"Gemini rate limit, ждём {wait} сек... (попытка {attempt + 1}/3)")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break
    else:
        print("Gemini недоступен (rate limit). Пропускаем этот запуск.")
        return {"signal": "нейтральный", "strength": 0, "key_factor": "rate limit",
                "action": "—", "risk": "—", "reasoning": "Gemini API временно недоступен",
                "education": "", "pattern": ""}

    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text.strip())


def _trading_prompt(instrument_name, price, indicators, position_text, news_text, history_text):
    tech_score   = indicators.get("tech_score", 0)
    tech_bias    = indicators.get("tech_bias", "нейтральный")
    tech_signals = indicators.get("tech_signals", [])
    tech_signals_text = "\n".join(f"  • {s}" for s in tech_signals) if tech_signals else "  нет данных"

    return f"""Ты — опытный трейдер. Дай торговый сигнал строго по правилам ниже.

══════════════════════════════════════════
ИНСТРУМЕНТ: {instrument_name}
══════════════════════════════════════════

ЦЕНА:
- Текущая: {price.get('mid')}
- Изменение за день: {price.get('change_pct')}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ТЕХНИЧЕСКИЙ АНАЛИЗ (ПЕРВИЧНЫЙ СИГНАЛ)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Технический скор: {tech_score:+d} из ±6
Технический перевес: {tech_bias}

Сигналы которые дали этот скор:
{tech_signals_text}

Дополнительные данные:
- RSI (14, дневной): {indicators.get('rsi', '—')}
- RSI (14, 4H): {indicators.get('rsi_4h', '—')}
- EMA20 / EMA50 (дневной): {indicators.get('ema20', '—')} / {indicators.get('ema50', '—')}
- Тренд EMA: {indicators.get('ema_trend', '—')}
- Тренд 4H: {indicators.get('trend_4h', '—')}
- MACD / Сигнал / Гистограмма: {indicators.get('macd_line', '—')} / {indicators.get('macd_signal', '—')} / {indicators.get('macd_hist', '—')}
- MACD перевес: {indicators.get('macd_bias', '—')}
- Боллинджер: верхняя {indicators.get('bb_upper', '—')} / середина {indicators.get('bb_middle', '—')} / нижняя {indicators.get('bb_lower', '—')}
- Позиция в полосе: {indicators.get('bb_position', '—')}
- Поддержка (20 дней): {indicators.get('support', '—')}
- Сопротивление (20 дней): {indicators.get('resistance', '—')}
- Пивот (вчерашний): {indicators.get('pivot', '—')}
- Свечной паттерн: {indicators.get('pattern', '—')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
НОВОСТИ (контекст, вторичный фактор)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{news_text if news_text else "Новостей нет."}

ПОЗИЦИЯ ТРЕЙДЕРА:
{position_text}

ИСТОРИЯ СИГНАЛОВ:
{history_text if history_text else "История пуста."}

══════════════════════════════════════════
ПРАВИЛА ФОРМИРОВАНИЯ СИГНАЛА (обязательны):
══════════════════════════════════════════
1. Поле "signal" ОПРЕДЕЛЯЕТСЯ техническим перевесом:
   - tech_score >= +2  → "бычий"
   - tech_score <= -2  → "медвежий"
   - -1 <= tech_score <= +1 → "нейтральный" (если нет паттерна разворота)
2. Новости могут изменить "strength" на ±1, но НЕ МОГУТ изменить направление signal если |tech_score| >= 2.
3. "strength" считается от |tech_score|: 1-2 → сила 2, 3-4 → сила 3-4, 5-6 → сила 5.
4. Если tech_score нейтральный но паттерн свечей даёт чёткий сигнал — используй паттерн как основу.

Ответь строго в формате JSON:
{{
  "signal": "бычий" | "медвежий" | "нейтральный",
  "strength": 1-5,
  "key_factor": "главный технический фактор прямо сейчас (1 предложение)",
  "action": "конкретная рекомендация с уровнями — где вход, где стоп, где цель",
  "risk": "главный риск и при каком сценарии он реализуется",
  "reasoning": "анализ (4-6 предложений) — опиши что показывают индикаторы, как они согласуются между собой, что означает паттерн, как новости усиливают или ослабляют сигнал",
  "education": "обучающий блок (2-3 предложения) — объясни простыми словами один конкретный индикатор из данных выше применительно к текущей ситуации",
  "pattern": "название паттерна если есть (например: бычье поглощение на поддержке, ложный пробой EMA50) — или пустая строка"
}}"""


def _digest_prompt(news_text):
    return f"""Ты — международный аналитик. Из потока новостей ниже составь дневной дайджест на русском языке.

Темы которые интересны: геополитика, дипломатия, саммиты, санкции, технологии, искусственный интеллект, энергетика, крупные сделки M&A, игровая индустрия, космос.
Темы которые НЕ интересны: мода, автомобили, спорт, светские новости, рецепты.

НОВОСТИ (последние 24 часа):
{news_text if news_text else "Новостей нет."}

Ответь строго в формате JSON (все поля на русском):
{{
  "key_factor": "главная тема дня — одно предложение",
  "reasoning": "подробный обзор важнейших событий (6-8 предложений) — что произошло, кто участвует, что это означает. Охвати разные темы: политику, технологии, энергетику, игры если есть.",
  "risk": "главный риск или неопределённость прямо сейчас — одно предложение",
  "action": "на что обратить внимание в ближайшие дни — одно предложение",
  "top_events": [
    "краткое описание события 1 (1-2 предложения)",
    "краткое описание события 2 (1-2 предложения)",
    "краткое описание события 3 (1-2 предложения)",
    "краткое описание события 4 (1-2 предложения)",
    "краткое описание события 5 (1-2 предложения)"
  ],
  "upcoming_events": [
    {{"event": "название события", "date": "дата или период", "location": "страна/город", "participants": ["участник1", "участник2"]}},
    {{"event": "название события", "date": "дата или период", "location": "страна/город", "participants": ["участник1"]}}
  ]
}}

upcoming_events — только конкретные запланированные события из новостей (саммиты, визиты лидеров, переговоры, конференции). Если дат нет — пустой массив [].
top_events — только то что реально произошло или происходит прямо сейчас."""
