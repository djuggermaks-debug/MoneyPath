import json
import yaml
import sys
import os
from datetime import datetime, timezone

from src.news import fetch_all
from src.market import get_market_data
from src.analysis import analyze
# from src.notifier import send_alert  # включить когда будет нужна почта
from src import memory


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state():
    with open("state.json", "r", encoding="utf-8") as f:
        return json.load(f)


def is_trading_hours(config):
    now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour
    minute = now_utc.minute
    current_minutes = hour * 60 + minute

    def to_minutes(time_str):
        h, m = map(int, time_str.split(":"))
        return h * 60 + m

    london_open = to_minutes(config["schedule"]["london_open_utc"])
    london_close = to_minutes(config["schedule"]["london_close_utc"])
    us_open = to_minutes(config["schedule"]["us_open_utc"])
    us_close = to_minutes(config["schedule"]["us_close_utc"])

    in_london = london_open <= current_minutes <= london_close
    in_us = us_open <= current_minutes <= us_close

    return in_london or in_us


def main():
    config = load_config()
    state = load_state()

    mode = state.get("mode", "trading")
    instrument_key = state.get("active_instrument", "OIL")

    instrument = config["instruments"].get(instrument_key)
    if not instrument:
        print(f"Инструмент {instrument_key} не найден в config.yaml")
        sys.exit(1)

    print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] Режим: {mode} | Инструмент: {instrument['name']}")

    if mode == "trading" and not is_trading_hours(config):
        print("Вне торговых часов. Пропускаем.")
        sys.exit(0)

    keywords = instrument["keywords"]
    news = fetch_all(keywords)
    print(f"Найдено новостей: {len(news)}")

    if not news and mode == "trading":
        print("Новостей нет. Пропускаем анализ.")
        sys.exit(0)

    market_data = get_market_data(instrument_key)
    current_price = market_data["price"].get("mid", 0)

    history = memory.load_history(instrument_key)
    memory.update_price_changes({instrument_key: current_price})

    result = analyze(instrument["name"], news, market_data, history)

    print(f"Сигнал: {result.get('signal')} | Сила: {result.get('strength')}/5")
    print(f"Фактор: {result.get('key_factor')}")

    min_strength = config["alerts"]["min_signal_strength"]
    if result.get("strength", 0) >= min_strength:
        save_alert(instrument["name"], instrument_key, result, market_data, news)
        # send_alert(instrument["name"], result, market_data, news)  # включить для почты
    else:
        print(f"Сигнал слабее {min_strength}/5. Пропускаем.")

    memory.save_signal(instrument_key, result, current_price)


def save_alert(instrument_name, instrument_key, analysis, market_data, news_articles):
    path = "data/alerts.json"
    os.makedirs("data", exist_ok=True)

    alerts = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            alerts = json.load(f)

    price = market_data.get("price", {})
    indicators = market_data.get("indicators", {})
    position = market_data.get("position")

    alerts.insert(0, {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "instrument": instrument_key,
        "instrument_name": instrument_name,
        "signal": analysis.get("signal"),
        "strength": analysis.get("strength"),
        "key_factor": analysis.get("key_factor"),
        "action": analysis.get("action"),
        "risk": analysis.get("risk"),
        "reasoning": analysis.get("reasoning"),
        "price": price.get("mid"),
        "change_pct": price.get("change_pct"),
        "rsi": indicators.get("rsi"),
        "support": indicators.get("support"),
        "resistance": indicators.get("resistance"),
        "position": position,
        "top_news": [{"title": a["title"], "source": a["source"], "link": a["link"]} for a in news_articles[:5]],
    })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(alerts[:50], f, ensure_ascii=False, indent=2)  # хранить последние 50

    print(f"Алерт сохранён в {path}")


if __name__ == "__main__":
    main()
