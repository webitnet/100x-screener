import asyncio
import httpx
from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)

DEFILLAMA_API = "https://api.llama.fi"


class OnChainAnalyzer(BaseModule):
    name = "onchain_analyzer"

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
                analysis = await self._analyse_one(client, cg_id, p)
                if analysis:
                    results.append(analysis)
                else:
                    warnings.append(f"No on-chain data for {cg_id}")
                await asyncio.sleep(0.5)  # DefiLlama is generous but be polite

        logger.info(f"OnChain: analysed {len(results)}/{len(projects)} projects")
        return self.ok(
            data={"analyses": results},
            message=f"Analysed {len(results)} projects",
            warnings=warnings or None,
        )

    async def _analyse_one(self, client: httpx.AsyncClient, cg_id: str, project: dict) -> dict | None:
        tvl_data = await self._fetch_defillama(client, cg_id)

        mcap = project.get("market_cap") or 0
        volume = project.get("volume_24h") or 0

        tvl = tvl_data.get("tvl") if tvl_data else None
        tvl_change_7d = tvl_data.get("tvl_change_7d") if tvl_data else None

        # Score (0-20)
        score = 0
        red_flags = []

        if tvl is not None:
            if tvl >= 10_000_000:
                score += 6
            elif tvl >= 1_000_000:
                score += 4
            elif tvl >= 100_000:
                score += 2

            if tvl_change_7d is not None:
                if tvl_change_7d > 20:
                    score += 4
                elif tvl_change_7d > 5:
                    score += 2
                elif tvl_change_7d < -20:
                    red_flags.append(f"TVL dropped {tvl_change_7d:.1f}% in 7d")

        if volume and mcap:
            vol_ratio = volume / mcap if mcap > 0 else 0
            if vol_ratio > 0.5:
                score += 5
            elif vol_ratio > 0.2:
                score += 3
            elif vol_ratio > 0.1:
                score += 1

        price_change = project.get("price_change_24h") or 0
        if price_change > 10:
            score += 3
        elif price_change > 0:
            score += 1

        # If no TVL data, still return with volume-based scores
        if tvl is None and score == 0:
            return None

        return {
            "project_id": cg_id,
            "tvl_usd": tvl,
            "tvl_change_7d_pct": tvl_change_7d,
            "market_cap": mcap,
            "volume_24h": volume,
            "onchain_score": min(score, 20),
            "red_flags": red_flags,
        }

    async def _fetch_defillama(self, client: httpx.AsyncClient, cg_id: str) -> dict | None:
        try:
            resp = await client.get(f"{DEFILLAMA_API}/protocol/{cg_id}")
            if resp.status_code != 200:
                return None
            data = resp.json()
            tvl = data.get("currentChainTvls", {})
            total_tvl = sum(v for k, v in tvl.items() if not k.endswith("-borrowed"))

            tvl_history = data.get("tvl", [])
            tvl_change_7d = None
            if len(tvl_history) >= 7:
                current = tvl_history[-1].get("totalLiquidityUSD", 0)
                week_ago = tvl_history[-7].get("totalLiquidityUSD", 0)
                if week_ago > 0:
                    tvl_change_7d = round((current - week_ago) / week_ago * 100, 2)

            return {"tvl": total_tvl, "tvl_change_7d": tvl_change_7d}
        except Exception:
            return None
