"""Alert rules: parsing user commands and deciding when an alert fires. Pure functions, no I/O."""
import re
from dataclasses import dataclass

# Common tickers -> CoinGecko ids. Any other CoinGecko id (e.g. "jupiter-exchange-solana") also works as is.
SYMBOLS = {
    "btc": "bitcoin", "eth": "ethereum", "sol": "solana", "ton": "the-open-network", "usdt": "tether",
    "usdc": "usd-coin", "bnb": "binancecoin", "xrp": "ripple", "doge": "dogecoin", "trx": "tron", "ada": "cardano",
    "avax": "avalanche-2", "link": "chainlink", "dot": "polkadot", "ltc": "litecoin", "not": "notcoin",
    "jup": "jupiter-exchange-solana", "bonk": "bonk", "wif": "dogwifcoin", "sui": "sui",
}
TICKER = {v: k.upper() for k, v in SYMBOLS.items()}


def coin_id(word: str) -> str:
    w = word.strip().lower()
    return SYMBOLS.get(w, w)


def ticker(cid: str) -> str:
    return TICKER.get(cid, cid)


@dataclass
class Rule:
    coin: str
    kind: str        # "above" | "below" | "up" | "down"
    value: float     # price in USD for above/below, percent for up/down


class ParseError(ValueError):
    pass


_RULE = re.compile(r"^\s*([a-z0-9-]+)\s*(>=|<=|>|<)?\s*([+-]?)\s*\$?([\d.,]+)\s*(%?)\s*$", re.I)


def parse_rule(text: str) -> Rule:
    """'sol > 200', 'ton < 2.5', 'btc +5%', 'eth -10%'."""
    m = _RULE.match(text)
    if not m:
        raise ParseError("Формат: <монета> > цена, <монета> < цена, <монета> +5% или <монета> -5%")
    word, op, sign, num, pct = m.groups()
    try:
        value = float(num.replace(",", "."))
    except ValueError:
        raise ParseError("Не понял число") from None
    if value <= 0:
        raise ParseError("Число должно быть больше нуля")
    if pct:
        if op:
            raise ParseError("Для процентов пишите так: sol +5% или sol -5%")
        if not sign:
            raise ParseError("Укажите направление: +5% (рост) или -5% (падение)")
        return Rule(coin_id(word), "up" if sign == "+" else "down", value)
    if sign or not op:
        raise ParseError("Для цены укажите > или <, например: sol > 200")
    return Rule(coin_id(word), "above" if op.startswith(">") else "below", value)


def fired(kind: str, value: float, base: float, price: float) -> bool:
    """Has the alert's condition been met? `base` is the price when the alert was created."""
    if kind == "above":
        return price >= value
    if kind == "below":
        return price <= value
    change = (price - base) / base * 100
    return change >= value if kind == "up" else change <= -value


def describe(kind: str, value: float, coin: str, base: float) -> str:
    t = ticker(coin)
    if kind == "above":
        return f"{t} ≥ ${fmt_price(value)}"
    if kind == "below":
        return f"{t} ≤ ${fmt_price(value)}"
    return f"{t} {'+' if kind == 'up' else '−'}{value:g}% от ${fmt_price(base)}"


def fmt_price(p: float) -> str:
    if p >= 1000:
        return f"{p:,.0f}".replace(",", " ")
    if p >= 1:
        return f"{p:.2f}"
    return f"{p:.6f}".rstrip("0")
