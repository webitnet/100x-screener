import asyncio
import httpx
from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)

GOPLUS_API = "https://api.gopluslabs.io/api/v1"

CHAIN_IDS = {
    "ethereum": "1",
    "binance-smart-chain": "56",
    "arbitrum-one": "42161",
    "base": "8453",
}


class WhaleDetector(BaseModule):
    name = "whale_detector"

    async def run(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        if not projects:
            return self.fail("No projects to analyse")

        results = []
        warnings = []
        async with httpx.AsyncClient(timeout=20) as client:
            for p in projects:
                cg_id = p.get("id")
                if not cg_id:
                    continue
                detail = (coin_details or {}).get(cg_id)
                if not detail:
                    warnings.append(f"No data for {cg_id}")
                    continue

                analysis = self._analyse_holders(cg_id, detail)
                if analysis:
                    results.append(analysis)
                else:
                    warnings.append(f"No whale data for {cg_id}")

        logger.info(f"WhaleDetector: analysed {len(results)}/{len(projects)} projects")
        return self.ok(
            data={"analyses": results},
            message=f"Analysed {len(results)} projects",
            warnings=warnings or None,
        )

    def _analyse_holders(self, cg_id: str, detail: dict) -> dict | None:
        market = detail.get("market_data") or {}
        mcap = market.get("market_cap", {}).get("usd") or 0
        volume = market.get("total_volume", {}).get("usd") or 0
        price_change_7d = market.get("price_change_percentage_7d") or 0
        price_change_30d = market.get("price_change_percentage_30d") or 0

        # Whale signals based on volume/mcap and price action
        signals = []
        score = 0

        # High volume relative to mcap = potential accumulation
        vol_ratio = volume / mcap if mcap > 0 else 0
        if vol_ratio > 1.0:
            signals.append(f"Extreme volume: {vol_ratio:.1f}x market cap")
            score += 3
        elif vol_ratio > 0.5:
            signals.append(f"High volume: {vol_ratio:.1f}x market cap")
            score += 2
        elif vol_ratio > 0.2:
            score += 1

        # Price momentum (potential smart money accumulation)
        if price_change_7d > 30:
            signals.append(f"Strong 7d momentum: +{price_change_7d:.0f}%")
            score += 2
        elif price_change_7d > 10:
            score += 1

        if price_change_30d > 100:
            signals.append(f"30d surge: +{price_change_30d:.0f}%")
            score += 2
        elif price_change_30d > 30:
            score += 1

        # Community interest proxy
        watchlist = detail.get("watchlist_portfolio_users") or 0
        if watchlist > 10000:
            signals.append(f"High watchlist: {watchlist:,} users")
            score += 2
        elif watchlist > 1000:
            score += 1

        return {
            "project_id": cg_id,
            "volume_to_mcap": round(vol_ratio, 4),
            "price_change_7d": price_change_7d,
            "price_change_30d": price_change_30d,
            "watchlist_users": watchlist,
            "whale_signals": signals,
            "smart_money_score": min(score, 5),  # max 5 points per ТЗ
            "red_flags": [],
        }
