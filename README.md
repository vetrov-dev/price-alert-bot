# Crypto Price Alert Bot

A Telegram bot that shows crypto prices on request and messages you when a coin crosses a price or moves by a
percent. Prices come from the CoinGecko public API.

The bot's interface is in Russian.

## Commands

| Command | Example | What it does |
|---|---|---|
| `/price` | `/price sol ton btc` | Current USD price and 24 h change |
| `/alert <coin> > <price>` | `/alert sol > 200` | Fires when the price reaches $200 or more |
| `/alert <coin> < <price>` | `/alert ton < 2.5` | Fires when the price drops to $2.5 or less |
| `/alert <coin> +N%` | `/alert btc +5%` | Fires after a 5% rise from the price at creation |
| `/alert <coin> -N%` | `/alert eth -10%` | Fires after a 10% drop |
| `/alerts` | | Your active alerts, tap one to delete it |

Coins: common tickers (BTC, ETH, SOL, TON, BNB, XRP, DOGE, TRX, NOT, JUP, BONK, WIF, …) or any CoinGecko id.

## How it works

- Alerts are stored in SQLite with the price at creation, so percent alerts measure from that point.
- One batched CoinGecko request per check for all coins that have active alerts, plus a 30 s cache, so the bot
  stays far inside the free API limits however many users it has.
- An alert whose condition is already true is refused with the current price, instead of firing instantly.
- Each alert fires once, then leaves the active list.
- Per-user alert limit, configurable.

## Stack

Python 3.11+, aiogram 3, aiohttp, aiosqlite, pytest.

## Run

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
cp .env.example .env                           # set BOT_TOKEN, optionally COINGECKO_API_KEY
python bot.py
```

## Tests

```bash
pip install pytest
pytest -q
```

Covers command parsing (valid and invalid input), firing conditions and price formatting.

Price data: [CoinGecko](https://www.coingecko.com).
