import os
import requests


# Capital.com API docs: https://open-api.capital.com/
# Для demo: https://demo-api-capital.backend-capital.com/api/v1
# Для live: https://api-capital.backend-capital.com/api/v1

BASE_URL = "https://api-capital.backend-capital.com/api/v1"


class CapitalClient:
    def __init__(self):
        self.api_key = os.environ["CAPITAL_API_KEY"]
        self.email = os.environ["CAPITAL_EMAIL"]
        self.password = os.environ["CAPITAL_PASSWORD"]
        self.cst = None
        self.security_token = None

    def _headers(self):
        return {
            "X-CAP-API-KEY": self.api_key,
            "CST": self.cst,
            "X-SECURITY-TOKEN": self.security_token,
            "Content-Type": "application/json",
        }

    def authenticate(self):
        resp = requests.post(
            f"{BASE_URL}/session",
            json={"identifier": self.email, "password": self.password, "encryptedPassword": False},
            headers={"X-CAP-API-KEY": self.api_key, "Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        self.cst = resp.headers.get("CST")
        self.security_token = resp.headers.get("X-SECURITY-TOKEN")

    def get_price(self, epic):
        resp = requests.get(
            f"{BASE_URL}/markets/{epic}",
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        snapshot = data.get("snapshot", {})
        return {
            "epic": epic,
            "bid": snapshot.get("bid"),
            "offer": snapshot.get("offer"),
            "mid": round((snapshot.get("bid", 0) + snapshot.get("offer", 0)) / 2, 3),
            "change_pct": snapshot.get("percentageChange"),
        }

    def get_candles(self, epic, resolution="MINUTE_30", count=48):
        # resolution: MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, HOUR_4, DAY
        resp = requests.get(
            f"{BASE_URL}/prices/{epic}",
            params={"resolution": resolution, "max": count},
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("prices", [])

    def get_positions(self):
        resp = requests.get(
            f"{BASE_URL}/positions",
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("positions", [])

    def get_market_data(self, epic):
        self.authenticate()
        price = self.get_price(epic)
        candles = self.get_candles(epic)
        positions = self.get_positions()

        active_position = next(
            (p for p in positions if p.get("market", {}).get("epic") == epic), None
        )

        indicators = _calculate_indicators(candles)

        return {
            "price": price,
            "indicators": indicators,
            "position": active_position,
        }


def _calculate_indicators(candles):
    if len(candles) < 14:
        return {}

    closes = []
    for c in candles:
        mid = c.get("closePrice", {})
        val = (mid.get("bid", 0) + mid.get("ask", 0)) / 2
        closes.append(val)

    rsi = _rsi(closes, 14)
    support, resistance = _support_resistance(closes)

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
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _support_resistance(closes, lookback=48):
    recent = closes[-lookback:]
    return min(recent), max(recent)
