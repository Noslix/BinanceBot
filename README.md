# Binance DCA Bot

This repository contains a basic example of a Dollar Cost Averaging (DCA) bot for long-term Bitcoin investment on Binance.

## Requirements

- Python 3.8+
- The `requests` package is not required; the script uses built-in modules.
- Binance API key and secret stored in a `.env` file.

## Usage

1. Create a `.env` file containing your credentials:

```
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
TELEGRAM_TOKEN=your_bot_token       # optional
TELEGRAM_CHAT_ID=your_chat_id       # optional
```

2. Run the bot:

```bash
python3 binance_dca_bot.py
```

By default the script will invest 100 USDT in BTC every week for 10 weeks. Edit `binance_dca_bot.py` if you want to change the amount, interval, or number of iterations.

When Telegram integration is enabled you can control the bot with the following commands:

- `pause` – suspend purchases
- `reprendre` – resume purchases
- `status` – display current balance
- `log X` – show the last X days of log entries
- `help` – list the commands

## Disclaimer

This code is provided for educational purposes only. Investing in cryptocurrencies involves risk. Use at your own discretion.
