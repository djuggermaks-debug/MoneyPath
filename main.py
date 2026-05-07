import json
import yaml
import sys
import os
from datetime import datetime, timezone

from src.news import fetch_all, fetch_digest
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
    mode = os.environ.get("MODE", "trading")

    if mode == "digest":
        run_digest()
    else:
        run_trading(config)


def run_digest():
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] Режим: дайджест")
    news = fetch_digest()
    print(f"Найдено новостей: {len(news)}")
    if not news:
        print("Новостей не найдено — продолжаем анализ без них.")
    result = analyze("Дайджест", news, {}, {}, "digest")
    print(f"Главная тема: {result.get('key_factor')}")
    save_digest(result, news)


def run_trading(config):
    instrument_key = os.environ.get("INSTRUMENT", "OIL")

    instrument = config["instruments"].get(instrument_key)
    if not instrument:
        print(f"Инструмент {instrument_key} не найден в config.yaml")
        sys.exit(1)

    print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] Режим: trading | Инструмент: {instrument['name']}")

    if not is_trading_hours(config):
        print("Вне торговых часов. Пропускаем.")
        sys.exit(0)

    keywords = instrument["keywords"]
    news = fetch_all(keywords)
    print(f"Найдено новостей: {len(news)}")

    if not news:
        print("Новостей не найдено — анализируем только по рыночным данным.")

    market_data = get_market_data(instrument_key)
    current_price = market_data["price"].get("mid", 0)

    history = memory.load_history(instrument_key)
    memory.update_price_changes({instrument_key: current_price})

    result = analyze(instrument["name"], news, market_data, history, "trading")

    print(f"Сигнал: {result.get('signal')} | Сила: {result.get('strength')}/5")
    print(f"Фактор: {result.get('key_factor')}")

    min_strength = config["alerts"]["min_signal_strength"]
    if result.get("strength", 0) >= min_strength:
        save_alert(instrument["name"], instrument_key, result, market_data, news)
        # send_alert(instrument["name"], result, market_data, news)  # включить для почты
    else:
        print(f"Сигнал слабее {min_strength}/5. Пропускаем.")

    memory.save_signal(instrument_key, result, current_price)


def save_digest(analysis, news_articles):
    path = "data/digest.json"
    os.makedirs("data", exist_ok=True)

    digest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "key_factor": analysis.get("key_factor"),
        "reasoning": analysis.get("reasoning"),
        "risk": analysis.get("risk"),
        "action": analysis.get("action"),
        "top_events": analysis.get("top_events", []),
        "upcoming_events": analysis.get("upcoming_events", []),
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)

    print(f"Дайджест сохранён в {path}")


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
