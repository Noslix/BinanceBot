import hmac
import hashlib
import time
import urllib.parse
import urllib.request
import json
import os
from datetime import datetime


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

from telegram_bot import TelegramBot

BASE_URL = "https://api.binance.com"

# Default trading parameters
TRADE_AMOUNT_EUR = 100.0
TRADE_THRESHOLD = 0.01  # 1%


def _sign_params(params, api_secret):
    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    signature = hmac.new(api_secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return query_string + f"&signature={signature}"


def _send_signed_request(http_method: str, url_path: str, payload: dict, api_key: str, api_secret: str):
    payload["timestamp"] = int(time.time() * 1000)
    query = _sign_params(payload, api_secret)
    url = f"{BASE_URL}{url_path}?{query}"
    req = urllib.request.Request(url, method=http_method)
    req.add_header("X-MBX-APIKEY", api_key)
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
        return json.loads(data)


def buy_bitcoin_eur(amount_eur: float, api_key: str, api_secret: str):
    payload = {
        "symbol": "BTCEUR",
        "side": "BUY",
        "type": "MARKET",
        "quoteOrderQty": amount_eur,
    }
    return _send_signed_request("POST", "/api/v3/order", payload, api_key, api_secret)


def sell_bitcoin_btc(amount_btc: float, api_key: str, api_secret: str):
    payload = {
        "symbol": "BTCEUR",
        "side": "SELL",
        "type": "MARKET",
        "quantity": amount_btc,
    }
    return _send_signed_request("POST", "/api/v3/order", payload, api_key, api_secret)


def get_market_prices() -> tuple[float, float]:
    """Return the current last price and 24h weighted average price."""
    url = f"{BASE_URL}/api/v3/ticker/24hr?symbol=BTCEUR"
    with urllib.request.urlopen(url) as resp:
        data = json.load(resp)
    return float(data["lastPrice"]), float(data["weightedAvgPrice"])


def get_account_summary(api_key: str, api_secret: str) -> str:
    data = _send_signed_request("GET", "/api/v3/account", {}, api_key, api_secret)
    balances = {b["asset"]: float(b["free"]) + float(b["locked"]) for b in data.get("balances", [])}
    btc = balances.get("BTC", 0.0)
    eur = balances.get("EUR", 0.0)
    return f"BTC: {btc} | EUR: {eur}"


def verify_connection(api_key: str, api_secret: str) -> str:
    """Check Binance connectivity and trading permissions without placing orders."""
    # Ping public API to ensure connectivity
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/v3/ping") as resp:
            resp.read()
    except Exception as e:
        return f"Erreur connexion: {e}"

    try:
        data = _send_signed_request("GET", "/api/v3/account", {}, api_key, api_secret)
        if not data.get("canTrade", True):
            return "Connexion OK mais trading désactivé"
    except Exception as e:
        return f"Erreur compte: {e}"

    return "Connexion Binance OK, trading possible"


PAUSED = False


def dollar_cost_average(amount_eur: float, interval_sec: int, iterations: int, api_key: str, api_secret: str, telegram: TelegramBot | None = None):
    next_time = time.time()
    for i in range(iterations):
        while True:
            if not PAUSED and time.time() >= next_time:
                break
            time.sleep(1)
        if telegram:
            telegram.send_message(f"Achat {i + 1}/{iterations} de {amount_eur} EUR de BTC")
            telegram.log(f"buy {amount_eur} EUR")
        try:
            response = buy_bitcoin_eur(amount_eur, api_key, api_secret)
            print("Order response:", response)
        except Exception as e:
            print("Error placing order:", e)
            if telegram:
                telegram.send_message(f"Erreur lors de l'achat: {e}")
        next_time += interval_sec


def hourly_trading_loop(amount_eur: float, threshold: float, api_key: str, api_secret: str, telegram: TelegramBot | None = None):
    """Check the market every hour and decide whether to buy or sell."""
    while True:
        while PAUSED:
            time.sleep(1)
        try:
            price, avg = get_market_prices()
        except Exception as e:
            print("Error fetching prices:", e)
            if telegram:
                telegram.send_message(f"Erreur prix: {e}")
            time.sleep(3600)
            continue

        action = None
        if price < avg * (1 - threshold):
            action = "buy"
        elif price > avg * (1 + threshold):
            action = "sell"

        if action == "buy":
            if telegram:
                telegram.send_message(f"Achat {amount_eur} EUR de BTC prix {price}")
                telegram.log(f"buy {amount_eur} @ {price}")
            try:
                buy_bitcoin_eur(amount_eur, api_key, api_secret)
            except Exception as e:
                print("Order error:", e)
                if telegram:
                    telegram.send_message(f"Erreur achat: {e}")
        elif action == "sell":
            qty = amount_eur / price
            if telegram:
                telegram.send_message(f"Vente {qty:.6f} BTC prix {price}")
                telegram.log(f"sell {qty:.6f} @ {price}")
            try:
                sell_bitcoin_btc(qty, api_key, api_secret)
            except Exception as e:
                print("Order error:", e)
                if telegram:
                    telegram.send_message(f"Erreur vente: {e}")

        time.sleep(3600)


def handle_command(text: str, api_key: str, api_secret: str, telegram: TelegramBot):
    global PAUSED
    cmd = text.strip().lower()
    if cmd == "pause":
        PAUSED = True
        telegram.send_message("Programme en pause")
        telegram.log("pause")
    elif cmd in ("reprendre", "resume"):
        if PAUSED:
            PAUSED = False
            status = verify_connection(api_key, api_secret)
            telegram.send_message(f"Programme repris. {status}")
            telegram.log("resume")
    elif cmd == "status":
        telegram.send_message(get_account_summary(api_key, api_secret))
    elif cmd.startswith("log"):
        parts = cmd.split()
        days = 1
        if len(parts) > 1 and parts[1].isdigit():
            days = int(parts[1])
        telegram.send_message(telegram.recent_logs(days))
    elif cmd in ("aide", "help"):
        telegram.send_message(
            "Commandes:\n"
            "pause - met le programme en pause\n"
            "reprendre - relance le programme\n"
            "status - affiche le statut\n"
            "log X - log des X derniers jours\n"
            "help - cette aide"
        )


if __name__ == "__main__":
    # Load environment variables from .env if available
    load_env()
    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_API_SECRET")
    if not API_KEY or not API_SECRET:
        raise SystemExit("Please set BINANCE_API_KEY and BINANCE_API_SECRET environment variables")

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID")
    telegram = None
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        telegram = TelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT)
        telegram.log("start")
        conn_msg = verify_connection(API_KEY, API_SECRET)
        telegram.send_message(
            f"Bot lancé. {conn_msg} {get_account_summary(API_KEY, API_SECRET)}"
        )
        telegram.start_polling(lambda text: handle_command(text, API_KEY, API_SECRET, telegram))

    try:
        hourly_trading_loop(
            amount_eur=TRADE_AMOUNT_EUR,
            threshold=TRADE_THRESHOLD,
            api_key=API_KEY,
            api_secret=API_SECRET,
            telegram=telegram,
        )
    finally:
        if telegram:
            telegram.send_message(f"Bot arrêté. {get_account_summary(API_KEY, API_SECRET)}")
            telegram.log("stop")
            telegram.stop_polling()

