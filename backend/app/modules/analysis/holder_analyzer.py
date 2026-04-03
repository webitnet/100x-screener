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


class HolderAnalyzer(BaseModule):
    name = "holder_analyzer"

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

                contract_info = self._get_contract(detail)
                if not contract_info:
                    warnings.append(f"No contract for {cg_id}")
                    continue

                analysis = await self._analyse(client, cg_id, contract_info)
                if analysis:
                    results.append(analysis)
                await asyncio.sleep(0.5)

        logger.info(f"Holders: analysed {len(results)}/{len(projects)} projects")
        return self.ok(
            data={"analyses": results},
            message=f"Analysed {len(results)} projects",
            warnings=warnings or None,
        )

    def _get_contract(self, detail: dict) -> dict | None:
        platforms = detail.get("platforms", {})
        for platform, address in platforms.items():
            if address and platform in CHAIN_IDS:
                return {"address": address, "chain_id": CHAIN_IDS[platform]}
        for platform, address in platforms.items():
            if address:
                return {"address": address, "chain_id": "1"}
        return None

    async def _analyse(self, client: httpx.AsyncClient, cg_id: str, contract_info: dict) -> dict | None:
        address = contract_info["address"]
        chain_id = contract_info["chain_id"]

        holder_data = await self._fetch_holder_data(client, chain_id, address)
        if not holder_data:
            return None

        top10_pct = holder_data.get("top10_pct", 0)
        total_holders = holder_data.get("holder_count", 0)

        red_flags = []
        score = 10

        if top10_pct > 60:
            red_flags.append(f"Top-10 holders own {top10_pct:.1f}% of supply")
            score -= 7
        elif top10_pct > 40:
            score -= 3
        elif top10_pct > 25:
            score -= 1

        if total_holders < 100:
            red_flags.append(f"Only {total_holders} holders")
            score -= 3

        score = max(0, score)

        return {
            "project_id": cg_id,
            "contract_address": address,
            "holder_count": total_holders,
            "top10_holder_pct": top10_pct,
            "holder_score": score,
            "red_flags": red_flags,
        }

    async def _fetch_holder_data(self, client: httpx.AsyncClient, chain_id: str, address: str) -> dict | None:
        try:
            resp = await client.get(
                f"{GOPLUS_API}/token_security/{chain_id}",
                params={"contract_addresses": address},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            result = data.get("result", {}).get(address.lower(), {})
            if not result:
                return None

            holders = result.get("holders", [])
            holder_count = int(result.get("holder_count", 0))

            top10_pct = 0.0
            for h in holders[:10]:
                try:
                    top10_pct += float(h.get("percent", 0)) * 100
                except (ValueError, TypeError):
                    pass

            return {"holder_count": holder_count, "top10_pct": round(top10_pct, 2)}
        except Exception as exc:
            logger.warning(f"Holder data fetch failed for {address}: {exc}")
            return None
