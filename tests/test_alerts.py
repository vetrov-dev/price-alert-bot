import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alerts import ParseError, Rule, describe, fired, fmt_price, parse_rule  # noqa: E402


@pytest.mark.parametrize("text, rule", [
    ("sol > 200", Rule("solana", "above", 200)),
    ("ton<2,5", Rule("the-open-network", "below", 2.5)),
    ("btc >= 100000", Rule("bitcoin", "above", 100000)),
    ("eth -10%", Rule("ethereum", "down", 10)),
    ("BTC +5 %", Rule("bitcoin", "up", 5)),
    ("jupiter-exchange-solana > $1.2", Rule("jupiter-exchange-solana", "above", 1.2)),
])
def test_parse(text, rule):
    assert parse_rule(text) == rule


@pytest.mark.parametrize("text", ["", "sol", "sol 200", "sol 5%", "sol > 5%", "sol > 0", "sol > abc"])
def test_parse_errors(text):
    with pytest.raises(ParseError):
        parse_rule(text)


def test_fired():
    assert fired("above", 200, 150, 200) and not fired("above", 200, 150, 199.9)
    assert fired("below", 2, 3, 1.9) and not fired("below", 2, 3, 2.1)
    assert fired("up", 5, 100, 105) and not fired("up", 5, 100, 104.9)
    assert fired("down", 10, 100, 90) and not fired("down", 10, 100, 91)


def test_format():
    assert fmt_price(104250.4) == "104 250"
    assert fmt_price(2.5) == "2.50"
    assert fmt_price(0.00001234) == "0.000012"
    assert describe("up", 5, "bitcoin", 100) == "BTC +5% от $100.00"
