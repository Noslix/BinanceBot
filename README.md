# Binance DCA Bot

This repository contains a basic example of a Dollar Cost Averaging (DCA) bot for long-term Bitcoin investment on Binance.

## Requirements

- Python 3.8+
- Binance API key and secret stored in a `.env` file.
- For the optional volatility bot install the `python-binance` package:
  ```bash
  pip install python-binance
  ```


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

By default the script invests 10% of your available EUR balance in BTC every week for 10 weeks. Edit `binance_dca_bot.py` if you want to change the percentage, interval, or number of iterations.


When Telegram integration is enabled you can control the bot with the following commands:

- `pause` – suspend purchases
- `reprendre` – resume purchases
- `status` – display current balance
- `log X` – show the last X days of log entries
- `help` – list the commands

## Volatility Bot

`volatility_bot.py` monitors the hourly BTC/EUR price using the official Binance
`Client`. If the price drops more than 3% compared to the price 12 hours before,
it buys 5 EUR of BTC (maximum one purchase per day). Events are logged to
`bot_volatilite.log` and the last purchase date is stored in
`last_purchase.json`.
The bot relies on the `python-binance` package which you can install with
`pip install python-binance`.


Run it with:

```bash
python3 volatility_bot.py
```

You can also launch it in a background thread from another Python program via
`start_volatility_bot(api_key, api_secret)`.

## Disclaimer

This code is provided for educational purposes only. Investing in cryptocurrencies involves risk. Use at your own discretion.
