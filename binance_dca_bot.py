import hmac
import hashlib
import time
import urllib.parse
import urllib.request
import json
import os
from datetime import datetime

from telegram_bot import TelegramBot

BASE_URL = "https://api.binance.com"


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


def buy_bitcoin_usdt(amount_usdt: float, api_key: str, api_secret: str):
    payload = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "MARKET",
        "quoteOrderQty": amount_usdt,
    }
    return _send_signed_request("POST", "/api/v3/order", payload, api_key, api_secret)


def get_account_summary(api_key: str, api_secret: str) -> str:
    data = _send_signed_request("GET", "/api/v3/account", {}, api_key, api_secret)
    balances = {b["asset"]: float(b["free"]) + float(b["locked"]) for b in data.get("balances", [])}
    btc = balances.get("BTC", 0.0)
    usdt = balances.get("USDT", 0.0)
    return f"BTC: {btc} | USDT: {usdt}"


PAUSED = False


def dollar_cost_average(amount_usdt: float, interval_sec: int, iterations: int, api_key: str, api_secret: str, telegram: TelegramBot | None = None):
    next_time = time.time()
    for i in range(iterations):
        while True:
            if not PAUSED and time.time() >= next_time:
                break
            time.sleep(1)
        if telegram:
            telegram.send_message(f"Achat {i + 1}/{iterations} de {amount_usdt} USDT de BTC")
            telegram.log(f"buy {amount_usdt} USDT")
        try:
            response = buy_bitcoin_usdt(amount_usdt, api_key, api_secret)
            print("Order response:", response)
        except Exception as e:
            print("Error placing order:", e)
            if telegram:
                telegram.send_message(f"Erreur lors de l'achat: {e}")
        next_time += interval_sec


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
            telegram.send_message("Programme repris")
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
    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_API_SECRET")
    if not API_KEY or not API_SECRET:
        raise SystemExit("Please set BINANCE_API_KEY and BINANCE_API_SECRET environment variables")

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID")
    telegram = None
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        telegram = TelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT)
        telegram.log("start")
        telegram.send_message(f"Bot lancé. {get_account_summary(API_KEY, API_SECRET)}")
        telegram.start_polling(lambda text: handle_command(text, API_KEY, API_SECRET, telegram))

    try:
        # Example: invest 100 USDT every week for 10 weeks
        dollar_cost_average(
            amount_usdt=100,
            interval_sec=7 * 24 * 60 * 60,
            iterations=10,
            api_key=API_KEY,
            api_secret=API_SECRET,
            telegram=telegram,
        )
    finally:
        if telegram:
            telegram.send_message(f"Bot arrêté. {get_account_summary(API_KEY, API_SECRET)}")
            telegram.log("stop")
            telegram.stop_polling()

