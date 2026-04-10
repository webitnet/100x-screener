import asyncio
import httpx
from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)

COINGECKO_API = "https://api.coingecko.com/api/v3"

MAX_MARKET_CAP = 50_000_000      # $50M
MIN_VOLUME_TO_MCAP_RATIO = 0.10  # 10%


class CoinGeckoScanner(BaseModule):
    name = "coingecko_scanner"

    async def run(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        try:
            coins = await self._fetch_candidates()
            filtered = self._apply_filters(coins)
            projects = [self._to_project(c) for c in filtered]
            logger.info(f"CoinGecko: {len(coins)} fetched, {len(projects)} passed filters")
            return self.ok(
                data={"projects": projects},
                message=f"Found {len(projects)} candidates",
            )
        except httpx.TimeoutException:
            return self.fail("CoinGecko API timeout")
        except httpx.HTTPStatusError as exc:
            return self.fail(f"CoinGecko HTTP error: {exc.response.status_code}")
        except Exception as exc:
            logger.error(f"CoinGeckoScanner unexpected error: {exc}", exc_info=True)
            return self.fail(str(exc))

    async def _fetch_candidates(self) -> list[dict]:
        """Fetch coins sorted by market_cap_desc from pages where small-caps appear."""
        all_coins: list[dict] = []
        # Free CoinGecko: ~30 req/min.
        # Pages 2-20 cover ranks ~250-5000 for full coverage.
        pages = list(range(2, 21))
        async with httpx.AsyncClient(timeout=20) as client:
            for page in pages:
                params = {
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 250,
                    "page": page,
                    "sparkline": False,
                    "price_change_percentage": "24h",
                }
                try:
                    resp = await client.get(f"{COINGECKO_API}/coins/markets", params=params)
                    resp.raise_for_status()
                    batch = resp.json()
                    if not batch:
                        break
                    all_coins.extend(batch)
                    logger.info(f"CoinGecko page {page}: fetched {len(batch)} coins")
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        logger.warning("CoinGecko rate limit hit, stopping pagination")
                        break
                    raise
                await asyncio.sleep(2)  # respect rate limits
        return all_coins

    def _apply_filters(self, coins: list[dict]) -> list[dict]:
        passed = []
        for coin in coins:
            mcap = coin.get("market_cap") or 0
            volume = coin.get("total_volume") or 0

            if mcap <= 0 or mcap > MAX_MARKET_CAP:
                continue

            if mcap > 0 and (volume / mcap) < MIN_VOLUME_TO_MCAP_RATIO:
                continue

            passed.append(coin)
        return passed

    def _to_project(self, coin: dict) -> dict:
        mcap = coin.get("market_cap") or 0
        volume = coin.get("total_volume") or 0
        return {
            "id": coin.get("id"),
            "name": coin.get("name"),
            "ticker": (coin.get("symbol") or "").upper(),
            "price": coin.get("current_price"),
            "market_cap": mcap,
            "volume_24h": volume,
            "volume_to_mcap_ratio": round(volume / mcap, 4) if mcap else None,
            "age_days": None,
            "price_change_24h": coin.get("price_change_percentage_24h"),
            "image": coin.get("image"),
            "source": "coingecko",
        }
