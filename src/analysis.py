import os
import json
import google.generativeai as genai


def analyze(instrument_name, news_articles, market_data, history):
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-1.5-flash")

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
        last = history[-5:]
        for h in last:
            history_text += f"- {h.get('date')}: сигнал {h.get('signal')}, цена изменилась на {h.get('price_change_4h', '?')}\n"

    prompt = f"""Ты — аналитик финансовых рынков. Анализируй данные и давай чёткий торговый сигнал.

ИНСТРУМЕНТ: {instrument_name}

РЫНОЧНЫЕ ДАННЫЕ:
- Текущая цена: {price.get('mid')}
- Изменение за день: {price.get('change_pct')}%
- RSI (30m): {indicators.get('rsi')}
- Поддержка: {indicators.get('support')}
- Сопротивление: {indicators.get('resistance')}

ПОЗИЦИЯ ТРЕЙДЕРА:
{position_text}

НОВОСТИ (последние 4 часа):
{news_text if news_text else "Новостей нет."}

ИСТОРИЯ ПРОШЛЫХ СИГНАЛОВ:
{history_text if history_text else "История пуста."}

Ответь строго в формате JSON:
{{
  "signal": "бычий" | "медвежий" | "нейтральный",
  "strength": 1-5,
  "reasoning": "краткое объяснение на русском (2-3 предложения)",
  "key_factor": "главный фактор который двигает цену прямо сейчас",
  "action": "конкретная рекомендация (например: ждать пробоя X, или осторожно — позиция под угрозой)",
  "risk": "главный риск прямо сейчас"
}}"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text.strip())
