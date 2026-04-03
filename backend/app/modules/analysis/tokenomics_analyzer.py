from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)


class TokenomicsAnalyzer(BaseModule):
    name = "tokenomics_analyzer"

    async def run(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        if not projects:
            return self.fail("No projects to analyse")

        results = []
        warnings = []
        for p in projects:
            cg_id = p.get("id")
            if not cg_id:
                continue
            detail = (coin_details or {}).get(cg_id)
            if not detail:
                warnings.append(f"No data for {cg_id}")
                continue
            results.append(self._extract_tokenomics(cg_id, detail))

        logger.info(f"Tokenomics: analysed {len(results)}/{len(projects)} projects")
        return self.ok(
            data={"analyses": results},
            message=f"Analysed {len(results)} projects",
            warnings=warnings or None,
        )

    def _extract_tokenomics(self, coingecko_id: str, data: dict) -> dict:
        market = data.get("market_data") or {}

        mcap = market.get("market_cap", {}).get("usd") or 0
        fdv = market.get("fully_diluted_valuation", {}).get("usd") or 0
        circulating = market.get("circulating_supply") or 0
        total_supply = market.get("total_supply") or 0
        max_supply = market.get("max_supply")

        fdv_to_mcap = round(fdv / mcap, 2) if mcap > 0 and fdv > 0 else None
        circ_to_total = round(circulating / total_supply, 4) if total_supply > 0 else None
        circ_to_max = round(circulating / max_supply, 4) if max_supply and max_supply > 0 else None

        red_flags = []
        if fdv_to_mcap and fdv_to_mcap > 10:
            red_flags.append(f"FDV/MCap = {fdv_to_mcap}x (>10x = high dilution risk)")
        if circ_to_total and circ_to_total < 0.1:
            red_flags.append(f"Only {circ_to_total:.1%} of supply circulating")

        score = 20
        if fdv_to_mcap:
            if fdv_to_mcap > 10:
                score -= 10
            elif fdv_to_mcap > 5:
                score -= 5
            elif fdv_to_mcap > 3:
                score -= 2
        if circ_to_total:
            if circ_to_total < 0.1:
                score -= 6
            elif circ_to_total < 0.3:
                score -= 3
        score = max(0, score)

        return {
            "project_id": coingecko_id,
            "name": data.get("name"),
            "market_cap_usd": mcap,
            "fdv_usd": fdv,
            "fdv_to_mcap": fdv_to_mcap,
            "circulating_supply": circulating,
            "total_supply": total_supply,
            "max_supply": max_supply,
            "circulating_to_total": circ_to_total,
            "circulating_to_max": circ_to_max,
            "tokenomics_score": score,
            "red_flags": red_flags,
        }
