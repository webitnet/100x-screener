import asyncio
import httpx
from datetime import datetime, timezone
from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)

DEXSCREENER_API = "https://api.dexscreener.com"

# Discovery filters
MAX_MARKET_CAP = 50_000_000
MIN_LIQUIDITY = 10_000
MIN_VOLUME_24H = 5_000
SUPPORTED_CHAINS = {"ethereum", "solana", "base", "arbitrum", "bsc"}


class DexScreenerScanner(BaseModule):
    name = "dexscreener_scanner"

    async def run(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        try:
            all_pairs = []
            warnings = []

            async with httpx.AsyncClient(timeout=20) as client:
                # Fetch trending / boosted tokens
                trending = await self._fetch_trending(client)
                all_pairs.extend(trending)

                # Fetch latest token profiles
                latest = await self._fetch_latest_profiles(client)
                all_pairs.extend(latest)

            filtered = self._apply_filters(all_pairs)
            projects_out = self._deduplicate([self._to_project(p) for p in filtered])

            logger.info(f"DexScreener: {len(all_pairs)} fetched, {len(projects_out)} passed filters")
            return self.ok(
                data={"projects": projects_out},
                message=f"Found {len(projects_out)} candidates from DexScreener",
                warnings=warnings or None,
            )
        except Exception as exc:
            logger.error(f"DexScreenerScanner error: {exc}", exc_info=True)
            return self.fail(str(exc))

    async def _fetch_trending(self, client: httpx.AsyncClient) -> list[dict]:
        """Fetch boosted/trending tokens from DexScreener."""
        try:
            resp = await client.get(f"{DEXSCREENER_API}/token-boosts/top/v1")
            if resp.status_code != 200:
                return []
            data = resp.json()
            # Returns list of {chainId, tokenAddress, ...}
            tokens = data if isinstance(data, list) else []
            pairs = []
            # Fetch pair data for each token (batch by chain)
            for token in tokens[:30]:  # limit to avoid rate issues
                chain = token.get("chainId", "")
                address = token.get("tokenAddress", "")
                if chain and address:
                    pair_data = await self._fetch_pair(client, chain, address)
                    pairs.extend(pair_data)
                    await asyncio.sleep(0.3)
            return pairs
        except Exception as exc:
            logger.warning(f"DexScreener trending fetch failed: {exc}")
            return []

    async def _fetch_latest_profiles(self, client: httpx.AsyncClient) -> list[dict]:
        """Fetch latest token profiles."""
        try:
            resp = await client.get(f"{DEXSCREENER_API}/token-profiles/latest/v1")
            if resp.status_code != 200:
                return []
            data = resp.json()
            tokens = data if isinstance(data, list) else []
            pairs = []
            for token in tokens[:20]:
                chain = token.get("chainId", "")
                address = token.get("tokenAddress", "")
                if chain and address:
                    pair_data = await self._fetch_pair(client, chain, address)
                    pairs.extend(pair_data)
                    await asyncio.sleep(0.3)
            return pairs
        except Exception as exc:
            logger.warning(f"DexScreener latest profiles failed: {exc}")
            return []

    async def _fetch_pair(self, client: httpx.AsyncClient, chain: str, address: str) -> list[dict]:
        try:
            resp = await client.get(f"{DEXSCREENER_API}/tokens/v1/{chain}/{address}")
            if resp.status_code != 200:
                return []
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _apply_filters(self, pairs: list[dict]) -> list[dict]:
        passed = []
        for pair in pairs:
            chain = (pair.get("chainId") or "").lower()
            if chain not in SUPPORTED_CHAINS:
                continue

            mcap = pair.get("marketCap") or pair.get("fdv") or 0
            if mcap <= 0 or mcap > MAX_MARKET_CAP:
                continue

            liquidity = (pair.get("liquidity") or {}).get("usd") or 0
            if liquidity < MIN_LIQUIDITY:
                continue

            volume_24h = (pair.get("volume") or {}).get("h24") or 0
            if volume_24h < MIN_VOLUME_24H:
                continue

            passed.append(pair)
        return passed

    def _to_project(self, pair: dict) -> dict:
        mcap = pair.get("marketCap") or pair.get("fdv") or 0
        volume = (pair.get("volume") or {}).get("h24") or 0
        liquidity = (pair.get("liquidity") or {}).get("usd") or 0
        price_change = (pair.get("priceChange") or {}).get("h24") or 0

        base_token = pair.get("baseToken") or {}
        return {
            "id": f"dex-{base_token.get('address', '')[:12]}",
            "name": base_token.get("name", "Unknown"),
            "ticker": base_token.get("symbol", "???"),
            "price": float(pair.get("priceUsd") or 0),
            "market_cap": mcap,
            "volume_24h": volume,
            "volume_to_mcap_ratio": round(volume / mcap, 4) if mcap > 0 else None,
            "liquidity_usd": liquidity,
            "price_change_24h": price_change,
            "chain": pair.get("chainId"),
            "dex_url": pair.get("url"),
            "pair_address": pair.get("pairAddress"),
            "image": pair.get("info", {}).get("imageUrl") if pair.get("info") else None,
            "source": "dexscreener",
        }

    def _deduplicate(self, projects: list[dict]) -> list[dict]:
        seen: dict[str, dict] = {}
        for p in projects:
            key = p.get("ticker", "") + "-" + (p.get("chain") or "")
            if key not in seen:
                seen[key] = p
        return list(seen.values())
