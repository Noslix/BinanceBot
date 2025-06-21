# Binance DCA Bot

This repository contains a simple Bitcoin trading bot for Binance.  It can perform
hourly buys or sells based on market conditions and also includes an optional
Dollar Cost Averaging (DCA) helper.

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

The default behaviour of `binance_dca_bot.py` is now to check the market once
per hour and either buy or sell a fixed amount depending on the current price
relative to the Binance 24‑hour weighted average price.  The amount traded and
the threshold used to trigger a trade can be changed by editing the
`TRADE_AMOUNT_USDT` and `TRADE_THRESHOLD` constants in `binance_dca_bot.py`.

The previous DCA logic is still available through the `dollar_cost_average`
function should you wish to use it instead.

When Telegram integration is enabled you can control the bot with the following commands:

- `pause` – suspend purchases
- `reprendre` – resume purchases
- `status` – display current balance
- `log X` – show the last X days of log entries
- `help` – list the commands

## Disclaimer

This code is provided for educational purposes only. Investing in cryptocurrencies involves risk. Use at your own discretion.
