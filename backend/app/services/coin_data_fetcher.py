import asyncio
import httpx
from app.core.logger import get_logger

logger = get_logger(__name__)

COINGECKO_API = "https://api.coingecko.com/api/v3"

MAX_RETRIES = 3
RATE_LIMIT_PAUSE = 65  # seconds to wait when rate limited


async def fetch_coin_details(coingecko_ids: list[str]) -> dict[str, dict]:
    """Fetch detailed coin data from CoinGecko once, for all modules to share.
    Retries on rate limit with backoff."""
    result = {}
    async with httpx.AsyncClient(timeout=20) as client:
        for cg_id in coingecko_ids:
            data = await _fetch_one(client, cg_id)
            if data:
                result[cg_id] = data
            await asyncio.sleep(2.5)
    return result


async def _fetch_one(client: httpx.AsyncClient, cg_id: str) -> dict | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(
                f"{COINGECKO_API}/coins/{cg_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "community_data": "false",
                    "developer_data": "true",
                    "sparkline": "false",
                },
            )
            if resp.status_code == 429:
                logger.warning(
                    f"Rate limited on {cg_id}, waiting {RATE_LIMIT_PAUSE}s (attempt {attempt + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(RATE_LIMIT_PAUSE)
                continue
            resp.raise_for_status()
            logger.info(f"Fetched details for {cg_id}")
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(f"HTTP error for {cg_id}: {exc.response.status_code}")
            return None
        except Exception as exc:
            logger.warning(f"Failed to fetch {cg_id}: {exc}")
            return None
    logger.error(f"Gave up fetching {cg_id} after {MAX_RETRIES} retries")
    return None
