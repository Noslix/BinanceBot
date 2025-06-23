
import time
import os
from decimal import Decimal
from typing import Optional


from binance.client import Client
from binance.exceptions import BinanceAPIException


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


MIN_NOTIONAL = 0.0


def fetch_trade_rules(client: Client, symbol: str = "BTCEUR") -> None:
    """Retrieve trading rules such as minimum notional."""
    global MIN_NOTIONAL
    try:
        info = client.get_symbol_info(symbol)
        if info:
            for f in info.get("filters", []):
                if f.get("filterType") == "MIN_NOTIONAL":
                    MIN_NOTIONAL = float(f.get("minNotional", 0))
                    break
    except Exception:
        MIN_NOTIONAL = 0.0


def get_min_notional(client: Client, symbol: str = "BTCEUR") -> float:
    """Return the minimum notional for a symbol or 0."""
    try:
        info = client.get_symbol_info(symbol)
        if info:
            for f in info.get("filters", []):
                if f.get("filterType") == "MIN_NOTIONAL":
                    return float(f.get("minNotional", 0))
    except Exception:
        pass
    return 0.0


def create_client(api_key: str, api_secret: str) -> Client:
    """Create a Binance Client instance."""
    return Client(api_key, api_secret)


def get_eur_balance(client: Client) -> float:
    """Return the available EUR balance (free funds)."""
    account = client.get_account()
    for b in account.get("balances", []):

        if b["asset"] == "EUR":
            return float(b["free"])
    return 0.0


def buy_bitcoin_eur(amount_eur: float, client: Client):
    """Place a market buy order on the BTCEUR pair."""
    qty = float(Decimal(amount_eur).quantize(Decimal("0.01")))
    return client.create_order(
        symbol="BTCEUR",
        side="BUY",
        type="MARKET",
        quoteOrderQty=qty,

    )


def get_account_summary(client: Client) -> str:
    """Return a short summary of BTC and EUR balances and open orders."""
    account = client.get_account()
    balances = {b["asset"]: (float(b["free"]) + float(b["locked"])) for b in account.get("balances", [])}
    btc = balances.get("BTC", 0.0)
    eur = balances.get("EUR", 0.0)
    orders = client.get_open_orders(symbol="BTCEUR")
    return f"BTC: {btc} | EUR: {eur} | Ordres en cours: {len(orders)}"



PAUSED = False


def dollar_cost_average(
    budget_ratio: float,
    interval_sec: int,
    iterations: int,
    client: Client,
    telegram: Optional[TelegramBot] = None,

):
    """Buy BTC with a percentage of the available EUR balance on a schedule."""
    next_time = time.time()
    for i in range(iterations):
        while True:
            if not PAUSED and time.time() >= next_time:
                break
            time.sleep(1)
        if MIN_NOTIONAL == 0:
            fetch_trade_rules(client)

        amount_eur = get_eur_balance(client) * budget_ratio
        if MIN_NOTIONAL and amount_eur < MIN_NOTIONAL:
            if telegram:
                telegram.send_message(
                    f"Montant {amount_eur:.2f} EUR < minimum {MIN_NOTIONAL} EUR, achat ignor\u00e9"
                )
                telegram.log("skip too small")
            next_time += interval_sec
            continue

        if telegram:
            telegram.send_message(
                f"Achat {i + 1}/{iterations} de {amount_eur:.2f} EUR de BTC"
            )
            telegram.log(f"buy {amount_eur:.2f} EUR")
        try:
            response = buy_bitcoin_eur(float(Decimal(amount_eur).quantize(Decimal('0.01'))), client)
            print("Order response:", response)
        except BinanceAPIException as e:
            print("Binance error:", e)
            if telegram:
                telegram.send_message(f"Erreur lors de l'achat: {e.message}")
                if "NOTIONAL" in e.message.upper() and MIN_NOTIONAL == 0:
                    telegram.send_message("R\u00e9cup\u00e9ration du minimum d'achat et nouvelle tentative la prochaine fois")
        except Exception as e:
            print("Unexpected error:", e)

            if telegram:
                telegram.send_message(f"Erreur lors de l'achat: {e}")
        next_time += interval_sec


def handle_command(text: str, client: Client, telegram: TelegramBot):
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
        telegram.send_message(get_account_summary(client))

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

    client = create_client(API_KEY, API_SECRET)
    fetch_trade_rules(client)

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

    TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID")
    telegram = None
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        telegram = TelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT)
        telegram.log("start")
        telegram.send_message(f"Bot lancé. {get_account_summary(client)}")
        telegram.start_polling(lambda text: handle_command(text, client, telegram))


    try:
        # Example: invest 10% of EUR balance every week for 10 weeks
        dollar_cost_average(
            budget_ratio=0.10,
            interval_sec=7 * 24 * 60 * 60,
            iterations=10,
            client=client,

            telegram=telegram,
        )
    finally:
        if telegram:
            telegram.send_message(f"Bot arrêté. {get_account_summary(client)}")
            telegram.log("stop")
            telegram.stop_polling()

