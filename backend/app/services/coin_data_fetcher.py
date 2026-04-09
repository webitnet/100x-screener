import asyncio
import httpx
from app.core.logger import get_logger

logger = get_logger(__name__)

COINGECKO_API = "https://api.coingecko.com/api/v3"

MAX_RETRIES = 5
RATE_LIMIT_PAUSE = 65  # seconds to wait when rate limited
REQUEST_DELAY = 6  # seconds between requests (free tier: ~10 req/min safe)

# DexScreener chainId → CoinGecko asset_platform_id
CHAIN_TO_PLATFORM = {
    "ethereum": "ethereum",
    "solana": "solana",
    "bsc": "binance-smart-chain",
    "base": "base",
    "arbitrum": "arbitrum-one",
    "polygon": "polygon-pos",
    "avalanche": "avalanche",
    "optimism": "optimistic-ethereum",
}


async def fetch_coin_details(
    coingecko_ids: list[str],
    projects: list[dict] | None = None,
) -> dict[str, dict]:
    """Fetch detailed coin data from CoinGecko once, for all modules to share.
    For dex-* IDs, resolves CoinGecko ID via contract address lookup."""
    # Build lookup for dex projects: dex-id → {chain, contract_address}
    dex_lookup: dict[str, dict] = {}
    if projects:
        for p in projects:
            pid = p.get("id", "")
            addr = p.get("contract_address", "")
            if pid.startswith("dex-") and p.get("chain") and addr:
                dex_lookup[pid] = {
                    "chain": p["chain"],
                    "address": addr,
                }
        if dex_lookup:
            logger.info(f"Dex projects to resolve by contract: {len(dex_lookup)}")

    result = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for idx, cg_id in enumerate(coingecko_ids):
            if cg_id.startswith("dex-") and cg_id in dex_lookup:
                # Resolve via contract address
                info = dex_lookup[cg_id]
                data = await _fetch_by_contract(
                    client, info["chain"], info["address"]
                )
                if data:
                    result[cg_id] = data
            else:
                data = await _fetch_one(client, cg_id)
                if data:
                    result[cg_id] = data

            if idx < len(coingecko_ids) - 1:
                await asyncio.sleep(REQUEST_DELAY)
    logger.info(
        f"Fetched {len(result)}/{len(coingecko_ids)} coin details"
    )
    return result


async def _fetch_by_contract(
    client: httpx.AsyncClient, chain: str, contract_address: str
) -> dict | None:
    """Resolve a token by contract address via CoinGecko."""
    platform = CHAIN_TO_PLATFORM.get(chain.lower())
    if not platform or not contract_address:
        logger.warning(f"Cannot resolve contract: chain={chain}, addr={contract_address[:20]}")
        return None

    for attempt in range(3):
        try:
            resp = await client.get(
                f"{COINGECKO_API}/coins/{platform}/contract/{contract_address}",
            )
            if resp.status_code == 429:
                wait = RATE_LIMIT_PAUSE
                logger.warning(f"Rate limited on contract lookup, waiting {wait}s")
                await asyncio.sleep(wait)
                continue
            if resp.status_code == 404:
                logger.info(f"Contract not found on CoinGecko: {chain}/{contract_address[:20]}")
                return None
            resp.raise_for_status()
            data = resp.json()
            cg_id = data.get("id", "")
            logger.info(f"Resolved contract {contract_address[:12]} → {cg_id}")
            return data
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                await asyncio.sleep(15)
                continue
            return None
        except Exception as exc:
            logger.warning(f"Contract lookup failed: {exc}")
            if attempt < 2:
                await asyncio.sleep(10)
                continue
            return None
    return None


async def _fetch_one(client: httpx.AsyncClient, cg_id: str) -> dict | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(
                f"{COINGECKO_API}/coins/{cg_id}",
                params={
                    "localization": "false",
                    "tickers": "true",
                    "community_data": "true",
                    "developer_data": "true",
                    "sparkline": "false",
                },
            )
            if resp.status_code == 429:
                wait = RATE_LIMIT_PAUSE * (attempt + 1)
                logger.warning(
                    f"Rate limited on {cg_id}, "
                    f"waiting {wait}s "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(wait)
                continue
            if resp.status_code == 404:
                logger.warning(f"Coin not found on CoinGecko: {cg_id}")
                return None
            resp.raise_for_status()
            logger.info(f"Fetched details for {cg_id}")
            return resp.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            logger.warning(f"HTTP {status} for {cg_id} (attempt {attempt + 1})")
            if status == 429 or status >= 500:
                wait = RATE_LIMIT_PAUSE if status == 429 else 15
                await asyncio.sleep(wait)
                continue
            return None
        except Exception as exc:
            logger.warning(f"Failed to fetch {cg_id}: {exc} (attempt {attempt + 1})")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(10)
                continue
            return None
    logger.error(
        f"Gave up fetching {cg_id} after {MAX_RETRIES} retries"
    )
    return None
