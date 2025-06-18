import hmac
import hashlib
import time
import urllib.parse
import urllib.request
import json
import os

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


def dollar_cost_average(amount_usdt: float, interval_sec: int, iterations: int, api_key: str, api_secret: str):
    for i in range(iterations):
        print(f"Purchase {i + 1} / {iterations}")
        try:
            response = buy_bitcoin_usdt(amount_usdt, api_key, api_secret)
            print("Order response:", response)
        except Exception as e:
            print("Error placing order:", e)
        if i < iterations - 1:
            time.sleep(interval_sec)


if __name__ == "__main__":
    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_API_SECRET")
    if not API_KEY or not API_SECRET:
        raise SystemExit("Please set BINANCE_API_KEY and BINANCE_API_SECRET environment variables")

    # Example: invest 100 USDT every week for 10 weeks
    dollar_cost_average(amount_usdt=100, interval_sec=7 * 24 * 60 * 60, iterations=10, api_key=API_KEY, api_secret=API_SECRET)
