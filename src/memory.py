import json
import os
from datetime import datetime, timezone


HISTORY_FILE = "data/history.json"
GRAPH_FILE = "data/graph.json"


def _load(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_history(instrument):
    history = _load(HISTORY_FILE)
    return [h for h in history if h.get("instrument") == instrument]


def save_signal(instrument, analysis, price):
    history = _load(HISTORY_FILE)
    history.append({
        "instrument": instrument,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "signal": analysis.get("signal"),
        "strength": analysis.get("strength"),
        "price_at_signal": price,
        "key_factor": analysis.get("key_factor"),
        "price_change_4h": None,  # заполняется при следующем запуске
    })
    _save(HISTORY_FILE, history[-200:])  # хранить последние 200 записей


def update_price_changes(current_prices):
    """При каждом запуске проверяем прошлые сигналы без price_change_4h и заполняем."""
    history = _load(HISTORY_FILE)
    for record in history:
        if record.get("price_change_4h") is None and record.get("instrument") in current_prices:
            current = current_prices[record["instrument"]]
            past = record.get("price_at_signal")
            if past and past > 0:
                change = round(((current - past) / past) * 100, 2)
                record["price_change_4h"] = f"{change:+.2f}%"
    _save(HISTORY_FILE, history)


def update_graph(entities):
    """Добавляет новые сущности и связи в граф (для будущей визуализации)."""
    graph = _load(GRAPH_FILE)
    if not isinstance(graph, dict):
        graph = {"nodes": [], "edges": []}

    existing_nodes = {n["id"] for n in graph["nodes"]}
    existing_edges = {(e["source"], e["target"]) for e in graph["edges"]}

    for entity in entities.get("nodes", []):
        if entity["id"] not in existing_nodes:
            graph["nodes"].append(entity)
            existing_nodes.add(entity["id"])

    for edge in entities.get("edges", []):
        key = (edge["source"], edge["target"])
        if key not in existing_edges:
            graph["edges"].append(edge)
            existing_edges.add(key)

    _save(GRAPH_FILE, graph)
