import httpx
from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)

COINGECKO_API = "https://api.coingecko.com/api/v3"

# Top exchanges ranked by trust and impact on price ("Coinbase Effect", "Binance Effect")
TOP_TIER_EXCHANGES = {
    "binance", "coinbase", "kraken", "okx", "bybit", "upbit",
}
MID_TIER_EXCHANGES = {
    "kucoin", "gate_io", "htx", "bitfinex", "bitstamp", "crypto_com",
    "mexc", "bitget",
}


class ExchangeTracker(BaseModule):
    """Stage 4 — Exchange Listing Tracker.

    Checks which exchanges already list a token and scores
    listing breadth. More top-tier listings = higher catalyst potential.
    Uses CoinGecko tickers endpoint.
    """

    name = "exchange_tracker"

    async def run(
        self,
        projects: list[dict] | None = None,
        coin_details: dict | None = None,
    ) -> ModuleResult:
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
                tickers = detail.get("tickers", []) if detail else []

                analysis = self._analyse_listings(cg_id, tickers)
                results.append(analysis)

        logger.info(
            f"ExchangeTracker: analysed {len(results)}/{len(projects)} projects"
        )
        return self.ok(
            data={"analyses": results},
            message=f"Analysed {len(results)} projects",
            warnings=warnings or None,
        )

    def _analyse_listings(self, cg_id: str, tickers: list[dict]) -> dict:
        # Extract unique exchange IDs from tickers
        exchange_ids: set[str] = set()
        for t in tickers:
            market = t.get("market") or {}
            eid = market.get("identifier") or ""
            if eid:
                exchange_ids.add(eid.lower())

        top_listed = exchange_ids & TOP_TIER_EXCHANGES
        mid_listed = exchange_ids & MID_TIER_EXCHANGES
        total_exchanges = len(exchange_ids)

        signals = []
        score = 0

        # Top-tier listings (max 4 pts)
        if len(top_listed) >= 4:
            signals.append(f"Listed on {len(top_listed)} top-tier CEXes: {', '.join(sorted(top_listed))}")
            score += 4
        elif len(top_listed) >= 2:
            signals.append(f"Listed on {len(top_listed)} top-tier CEXes: {', '.join(sorted(top_listed))}")
            score += 3
        elif len(top_listed) == 1:
            signals.append(f"Listed on {list(top_listed)[0].title()}")
            score += 2

        # Not on any top exchange = potential future catalyst
        if len(top_listed) == 0 and total_exchanges > 0:
            signals.append("Not yet on top-tier CEX — potential listing catalyst ahead")
            score += 1  # bonus for upside potential

        # Mid-tier presence (max 2 pts)
        if len(mid_listed) >= 3:
            score += 2
        elif len(mid_listed) >= 1:
            score += 1

        # Exchange breadth (max 2 pts)
        if total_exchanges >= 20:
            signals.append(f"Wide distribution: {total_exchanges} exchanges")
            score += 2
        elif total_exchanges >= 10:
            score += 1

        # DEX-only flag
        red_flags = []
        if total_exchanges == 0:
            red_flags.append("Not listed on any tracked exchange")

        return {
            "project_id": cg_id,
            "total_exchanges": total_exchanges,
            "top_tier": sorted(top_listed),
            "mid_tier": sorted(mid_listed),
            "exchange_signals": signals,
            "exchange_score": min(score, 8),  # max 8 pts
            "red_flags": red_flags,
        }
