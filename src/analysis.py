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
        prompt = _digest_prompt(instrument_name, news_text)
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
    return f"""Ты — опытный трейдер и наставник. Анализируй данные и давай развёрнутый торговый сигнал с обучающим блоком.

ИНСТРУМЕНТ: {instrument_name}

РЫНОЧНЫЕ ДАННЫЕ:
- Текущая цена: {price.get('mid')}
- Изменение за день: {price.get('change_pct')}%
- RSI (15m): {indicators.get('rsi')}
- Поддержка: {indicators.get('support')}
- Сопротивление: {indicators.get('resistance')}
- Пивот: {indicators.get('pivot')}

ПОЗИЦИЯ ТРЕЙДЕРА:
{position_text}

НОВОСТИ (последние 4 часа):
{news_text if news_text else "Новостей нет."}

ИСТОРИЯ СИГНАЛОВ:
{history_text if history_text else "История пуста."}

Ответь строго в формате JSON:
{{
  "signal": "бычий" | "медвежий" | "нейтральный",
  "strength": 1-5,
  "key_factor": "главный фактор который двигает цену прямо сейчас (1 предложение)",
  "action": "конкретная рекомендация с уровнями — что смотреть, где вход, где стоп",
  "risk": "главный риск и при каком сценарии он реализуется",
  "reasoning": "полный анализ ситуации на русском (4-6 предложений) — что происходит, почему, что это значит для цены",
  "education": "обучающий блок (3-5 предложений) — объясни простыми словами один из использованных инструментов анализа. Например: что значит текущий RSI, как работает уровень поддержки в данной ситуации, или что такое паттерн который сейчас формируется",
  "pattern": "название торгового паттерна или ситуации если она есть (например: продажа на новостях, ложный пробой, накопление перед движением) — или пустая строка если паттерна нет"
}}"""


def _digest_prompt(instrument_name, news_text):
    return f"""Ты — финансовый аналитик и педагог. Составь информативный дайджест по теме.

ТЕМА: {instrument_name}

НОВОСТИ:
{news_text if news_text else "Новостей нет."}

Ответь строго в формате JSON:
{{
  "signal": "нейтральный",
  "strength": 0,
  "key_factor": "главная тема дайджеста",
  "action": "на что обратить внимание в ближайшее время",
  "risk": "главный риск или неопределённость",
  "reasoning": "подробный обзор ситуации (5-7 предложений) — что происходит, какие силы действуют, что это означает",
  "education": "образовательный блок (3-5 предложений) — объясни один важный концепт связанный с текущими событиями. Например: как работают санкции на нефтяном рынке, что такое контанго, почему ФРС влияет на золото",
  "pattern": ""
}}"""
