import os
import json
import time
import threading
import logging
from datetime import datetime, timedelta

MIN_NOTIONAL = 0.0

from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Optional


def load_env(path: str = ".env") -> None:
    """Load key=value pairs from a .env file into os.environ."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    except FileNotFoundError:
        pass



def get_min_notional(client: Client, symbol: str) -> float:
    try:
        info = client.get_symbol_info(symbol)
        if info:
            for f in info.get("filters", []):
                if f.get("filterType") == "MIN_NOTIONAL":
                    return float(f.get("minNotional", 0))
    except Exception:
        pass
    return 0.0



class VolatilityBot(threading.Thread):
    """Monitor BTC/EUR price and buy if it drops more than 3%."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        symbol: str = "BTCEUR",
        euro_amount: float = 5.0,
        log_file: str = "bot_volatilite.log",
        record_file: str = "last_purchase.json",
        check_interval: int = 3600,
        lookback_hours: int = 12,
    ) -> None:
        super().__init__(daemon=True)
        self.client = Client(api_key, api_secret)
        self.symbol = symbol
        self.euro_amount = euro_amount
        self.log_file = log_file
        self.record_file = record_file
        self.check_interval = check_interval
        self.lookback_hours = lookback_hours
        self._stop_event = threading.Event()
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format="%(asctime)s - %(message)s",
        )
        self._fetch_trade_rules()


    def stop(self) -> None:
        self._stop_event.set()

    def _fetch_trade_rules(self) -> None:
        """Retrieve minimum notional required for trading."""
        global MIN_NOTIONAL
        MIN_NOTIONAL = get_min_notional(self.client, self.symbol)


    # Connection check
    def api_connected(self) -> bool:
        try:
            self.client.ping()
            return True
        except Exception as e:
            logging.error("API connection failed: %s", e)
            return False

    # Record keeping
    def _get_last_purchase_date(self):
        try:
            with open(self.record_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "last_purchase" in data:
                    return datetime.strptime(data["last_purchase"], "%Y-%m-%d").date()
        except Exception:
            return None

    def _set_last_purchase_date(self, date_obj):
        with open(self.record_file, "w", encoding="utf-8") as f:
            json.dump({"last_purchase": date_obj.strftime("%Y-%m-%d")}, f)

    def _should_buy(self) -> bool:
        try:
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=Client.KLINE_INTERVAL_1HOUR,
                limit=self.lookback_hours + 1,
            )
            if len(klines) < self.lookback_hours + 1:
                logging.warning("Not enough kline data returned")
                return False
            price_then = float(klines[0][1])  # open price 12 hours ago
            price_now = float(klines[-1][4])  # last closing price
            drop = (price_now - price_then) / price_then
            logging.info("Price %.2f -> %.2f (%.2f%%)", price_then, price_now, drop * 100)
            return drop <= -0.03
        except BinanceAPIException as e:
            logging.error("Binance API error during kline fetch: %s", e)
        except Exception as e:
            logging.error("Unexpected error during kline fetch: %s", e)
        return False

    def _buy(self):
        try:
            if MIN_NOTIONAL == 0:
                self._fetch_trade_rules()

            if MIN_NOTIONAL and self.euro_amount < MIN_NOTIONAL:
                logging.info(
                    "Amount %.2f EUR below minimum %.2f EUR, skipping", self.euro_amount, MIN_NOTIONAL
                )
                return

            order = self.client.create_order(
                symbol=self.symbol,
                side="BUY",
                type="MARKET",
                quoteOrderQty=float(round(self.euro_amount, 2)),

            )
            logging.info("Bought %s: %s", self.symbol, order)
            self._set_last_purchase_date(datetime.utcnow().date())
        except BinanceAPIException as e:
            logging.error("Binance API error during buy: %s", e)
            if "NOTIONAL" in str(e).upper() and MIN_NOTIONAL == 0:
                logging.info("Retrying next time after retrieving min notional")

        except Exception as e:
            logging.error("Unexpected error during buy: %s", e)

    def check_market(self):
        if not self.api_connected():
            return
        today = datetime.utcnow().date()
        last_date = self._get_last_purchase_date()
        if last_date == today:
            logging.info("Already bought today")
            return
        if self._should_buy():
            self._buy()
        else:
            logging.info("No purchase condition met")

    def run(self) -> None:
        while not self._stop_event.is_set():
            self.check_market()
            for _ in range(self.check_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)


def start_volatility_bot(api_key: str, api_secret: str) -> VolatilityBot:
    """Helper to start the bot in its own thread."""
    bot = VolatilityBot(api_key, api_secret)
    bot.start()
    return bot


if __name__ == "__main__":
    load_env()
    key = os.getenv("BINANCE_API_KEY")
    secret = os.getenv("BINANCE_API_SECRET")
    if not key or not secret:
        raise SystemExit("Missing Binance credentials")
    bot = VolatilityBot(key, secret)
    bot.start()
    try:
        while bot.is_alive():
            bot.join(timeout=1)
    except KeyboardInterrupt:
        bot.stop()
        bot.join()
