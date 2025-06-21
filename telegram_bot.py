
"""Module de gestion du bot Telegram pour contrôler le trader Binance."""


import urllib.parse
import urllib.request
import json
import time
import threading
from datetime import datetime, timedelta


class TelegramBot:
    """Petit client Telegram très simple utilisant l'API HTTP."""

    def __init__(self, token: str, chat_id: str, log_file: str = "bot.log"):
        # Informations de connexion

        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.log_file = log_file
        self.offset = None
        # Variables internes pour le thread de polling

        self._polling_thread = None
        self._stop_event = threading.Event()

    def log(self, message: str):
        """Ajoute une entrée au fichier de log."""

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} - {message}\n")

    def send_message(self, text: str):
        """Envoie un message simple au chat Telegram."""

        data = urllib.parse.urlencode({"chat_id": self.chat_id, "text": text}).encode()
        req = urllib.request.Request(f"{self.api_url}/sendMessage", data=data)
        with urllib.request.urlopen(req) as resp:
            resp.read()
        self.log(f"sent: {text}")

    def get_updates(self):
        """Récupère les messages entrants via long polling."""

        params = {"timeout": 100}
        if self.offset:
            params["offset"] = self.offset
        url = f"{self.api_url}/getUpdates?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url) as resp:
            data = json.load(resp)
        if data.get("ok"):
            for update in data.get("result", []):
                self.offset = update["update_id"] + 1
                message = update.get("message")
                if message and "text" in message:
                    yield message["text"]

    def start_polling(self, handler):
        """Lance un thread qui appelle 'handler' pour chaque message reçu."""


        def _poll():
            while not self._stop_event.is_set():
                try:
                    for text in self.get_updates() or []:
                        handler(text)
                except Exception:
                    time.sleep(1)

        self._polling_thread = threading.Thread(target=_poll, daemon=True)
        self._polling_thread.start()

    def stop_polling(self):
        """Arrête proprement le thread de polling."""

        self._stop_event.set()
        if self._polling_thread:
            self._polling_thread.join(timeout=1)

    def recent_logs(self, days: int) -> str:
        """Retourne les entrées de log des 'days' derniers jours."""

        cutoff = datetime.utcnow() - timedelta(days=days)
        lines = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        ts_str, rest = line.split(" - ", 1)
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        if ts >= cutoff:
                            lines.append(line.strip())
                    except ValueError:
                        continue
        except FileNotFoundError:
            return "No logs found."
        return "\n".join(lines) if lines else "No recent logs."

