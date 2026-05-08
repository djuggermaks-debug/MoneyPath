import datetime
import enum
import json
import logging
import random
import re
import string
import time
import pandas as pd
from websocket import create_connection
import requests

logger = logging.getLogger(__name__)


class Interval(enum.Enum):
    in_1_minute   = "1"
    in_3_minute   = "3"
    in_5_minute   = "5"
    in_15_minute  = "15"
    in_30_minute  = "30"
    in_45_minute  = "45"
    in_1_hour     = "1H"
    in_2_hour     = "2H"
    in_3_hour     = "3H"
    in_4_hour     = "4H"
    in_daily      = "1D"
    in_weekly     = "1W"
    in_monthly    = "1M"


class TvDatafeed:
    __sign_in_url  = "https://www.tradingview.com/accounts/signin/"
    __ws_headers   = json.dumps({"Origin": "https://data.tradingview.com"})
    __signin_headers = {"Referer": "https://www.tradingview.com"}
    __ws_timeout   = 10

    def __init__(self, username=None, password=None):
        self.ws_debug = False
        self.token = self.__auth(username, password)
        if self.token is None:
            self.token = "unauthorized_user_token"
        self.ws = None
        self.session = self.__generate_session()
        self.chart_session = self.__generate_chart_session()

    def __auth(self, username, password):
        if username is None or password is None:
            return None
        data = {"username": username, "password": password, "remember": "on"}
        try:
            response = requests.post(self.__sign_in_url, data=data, headers=self.__signin_headers)
            return response.json()["user"]["auth_token"]
        except Exception:
            return None

    def __create_connection(self):
        self.ws = create_connection(
            "wss://data.tradingview.com/socket.io/websocket",
            headers=self.__ws_headers,
            timeout=self.__ws_timeout,
        )

    @staticmethod
    def __generate_session():
        return "qs_" + "".join(random.choice(string.ascii_lowercase) for _ in range(12))

    @staticmethod
    def __generate_chart_session():
        return "cs_" + "".join(random.choice(string.ascii_lowercase) for _ in range(12))

    @staticmethod
    def __prepend_header(st):
        return "~m~" + str(len(st)) + "~m~" + st

    @staticmethod
    def __construct_message(func, param_list):
        return json.dumps({"m": func, "p": param_list}, separators=(",", ":"))

    def __create_message(self, func, paramList):
        return self.__prepend_header(self.__construct_message(func, paramList))

    def __send_message(self, func, args):
        m = self.__create_message(func, args)
        self.ws.send(m)

    @staticmethod
    def __create_df(raw_data, symbol):
        try:
            out = re.search('"s":\[(.+?)\}\]', raw_data).group(1)
            x = out.split(',{"')
            data = []
            for xi in x:
                xi = re.split(r"\[|:|,|\]", xi)
                ts = datetime.datetime.fromtimestamp(float(xi[4]))
                row = [ts]
                for i in range(5, 10):
                    try:
                        row.append(float(xi[i]))
                    except (ValueError, IndexError):
                        row.append(0.0)
                data.append(row)
            df = pd.DataFrame(data, columns=["datetime", "open", "high", "low", "close", "volume"])
            df = df.set_index("datetime")
            df.insert(0, "symbol", value=symbol)
            return df
        except AttributeError:
            return None

    @staticmethod
    def __format_symbol(symbol, exchange, contract=None):
        if ":" in symbol:
            return symbol
        if contract is None:
            return f"{exchange}:{symbol}"
        if isinstance(contract, int):
            return f"{exchange}:{symbol}{contract}!"
        raise ValueError("not a valid contract")

    def get_hist(self, symbol, exchange="NSE", interval=None, n_bars=100, fut_contract=None, extended_session=False):
        if interval is None:
            interval = Interval.in_daily
        symbol = self.__format_symbol(symbol=symbol, exchange=exchange, contract=fut_contract)
        interval = interval.value

        # Новые сессии при каждом вызове — иначе повторный вызов на том же объекте конфликтует
        self.session = self.__generate_session()
        self.chart_session = self.__generate_chart_session()

        self.__create_connection()
        self.__send_message("set_auth_token", [self.token])
        self.__send_message("chart_create_session", [self.chart_session, ""])
        self.__send_message("quote_create_session", [self.session])
        self.__send_message("quote_set_fields", [self.session, "ch", "chp", "current_session",
            "description", "local_description", "language", "exchange", "fractional",
            "is_tradable", "lp", "lp_time", "minmov", "minmove2", "original_name",
            "pricescale", "pro_name", "short_name", "type", "update_mode", "volume",
            "currency_code", "rchp", "rtc"])
        self.__send_message("quote_add_symbols", [self.session, symbol, {"flags": ["force_permission"]}])
        self.__send_message("quote_fast_symbols", [self.session, symbol])
        self.__send_message("resolve_symbol", [self.chart_session, "symbol_1",
            '={"symbol":"' + symbol + '","adjustment":"splits","session":' +
            ('"regular"' if not extended_session else '"extended"') + "}"])
        self.__send_message("create_series", [self.chart_session, "s1", "s1", "symbol_1", interval, n_bars])
        self.__send_message("switch_timezone", [self.chart_session, "exchange"])

        raw_data = ""
        completed = False
        deadline = time.time() + 25  # максимум 25 секунд на весь запрос
        while time.time() < deadline:
            try:
                result = self.ws.recv()
                raw_data += result + "\n"
            except Exception as e:
                print(f"tvDatafeed recv exception: {type(e).__name__}: {e}")
                break
            if "series_completed" in result:
                completed = True
                break

        print(f"tvDatafeed series_completed={completed}, raw_data len={len(raw_data)}")
        if not completed:
            print(f"tvDatafeed raw_data sample: {raw_data[:400]}")

        return self.__create_df(raw_data, symbol)
