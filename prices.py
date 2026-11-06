"""CoinGecko public API: current USD prices and 24 h change, with a small cache."""
import os
import time

import aiohttp

API = "https://api.coingecko.com/api/v3/simple/price"
CACHE_SECONDS = 30


class PriceError(Exception):
    pass


class Prices:
    def __init__(self, http: aiohttp.ClientSession):
        self.http = http
        self.cache: dict[str, tuple[float, dict]] = {}
        key = os.getenv("COINGECKO_API_KEY", "").strip()      # optional free demo key, raises the rate limit
        self.headers = {"accept": "application/json", **({"x-cg-demo-api-key": key} if key else {})}

    async def get(self, ids: list[str]) -> dict[str, dict]:
        """{id: {"usd": price, "usd_24h_change": pct}} for the ids CoinGecko knows; unknown ids are left out."""
        now = time.time()
        need = [i for i in set(ids) if now - self.cache.get(i, (0, {}))[0] > CACHE_SECONDS]
        for i in range(0, len(need), 100):
            chunk = need[i:i + 100]
            params = {"ids": ",".join(chunk), "vs_currencies": "usd", "include_24hr_change": "true"}
            async with self.http.get(API, params=params, headers=self.headers,
                                     timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 429:
                    raise PriceError("CoinGecko rate limit, try again in a minute")
                if r.status != 200:
                    raise PriceError(f"CoinGecko HTTP {r.status}")
                data = await r.json()
            for cid in chunk:
                if cid in data and "usd" in data[cid]:
                    self.cache[cid] = (now, data[cid])
        return {i: self.cache[i][1] for i in ids if i in self.cache}
