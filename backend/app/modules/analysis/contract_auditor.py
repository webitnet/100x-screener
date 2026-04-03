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


class ContractAuditor(BaseModule):
    name = "contract_auditor"

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

                contract_info = self._get_contract_address(detail)
                if not contract_info:
                    warnings.append(f"No contract address for {cg_id}")
                    continue

                analysis = await self._audit(client, cg_id, contract_info)
                if analysis:
                    results.append(analysis)
                await asyncio.sleep(0.5)

        logger.info(f"ContractAudit: analysed {len(results)}/{len(projects)} projects")
        return self.ok(
            data={"analyses": results},
            message=f"Audited {len(results)} projects",
            warnings=warnings or None,
        )

    def _get_contract_address(self, detail: dict) -> dict | None:
        platforms = detail.get("platforms", {})
        for platform, address in platforms.items():
            if address and platform in CHAIN_IDS:
                return {"address": address, "chain_id": CHAIN_IDS[platform], "platform": platform}
        for platform, address in platforms.items():
            if address:
                return {"address": address, "chain_id": "1", "platform": platform}
        return None

    async def _audit(self, client: httpx.AsyncClient, cg_id: str, contract_info: dict) -> dict | None:
        address = contract_info["address"]
        chain_id = contract_info["chain_id"]
        security = await self._check_goplus(client, chain_id, address)

        red_flags = []
        score = 20

        if security:
            if security.get("is_honeypot"):
                red_flags.append("Honeypot detected")
                score -= 15
            if security.get("is_mintable"):
                red_flags.append("Mint function present")
                score -= 10
            if security.get("is_blacklisted"):
                red_flags.append("Blacklist function")
                score -= 5
            if security.get("can_take_back_ownership"):
                red_flags.append("Owner can reclaim ownership")
                score -= 5
            if security.get("is_proxy"):
                red_flags.append("Proxy contract")
                score -= 3
            if security.get("is_open_source") is False:
                red_flags.append("Contract not verified")
                score -= 10
            if security.get("buy_tax", 0) > 10:
                red_flags.append(f"High buy tax: {security['buy_tax']:.0f}%")
                score -= 5
            if security.get("sell_tax", 0) > 10:
                red_flags.append(f"High sell tax: {security['sell_tax']:.0f}%")
                score -= 5

        score = max(0, score)

        return {
            "project_id": cg_id,
            "contract_address": address,
            "platform": contract_info["platform"],
            "is_honeypot": security.get("is_honeypot") if security else None,
            "is_mintable": security.get("is_mintable") if security else None,
            "is_open_source": security.get("is_open_source") if security else None,
            "buy_tax": security.get("buy_tax") if security else None,
            "sell_tax": security.get("sell_tax") if security else None,
            "audit_score": score,
            "red_flags": red_flags,
        }

    async def _check_goplus(self, client: httpx.AsyncClient, chain_id: str, address: str) -> dict | None:
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

            def to_bool(val):
                return val == "1" if isinstance(val, str) else bool(val)

            def to_float(val):
                try:
                    return float(val) * 100
                except (ValueError, TypeError):
                    return 0

            return {
                "is_honeypot": to_bool(result.get("is_honeypot")),
                "is_mintable": to_bool(result.get("is_mintable")),
                "is_blacklisted": to_bool(result.get("is_blacklisted")),
                "is_proxy": to_bool(result.get("is_proxy")),
                "is_open_source": to_bool(result.get("is_open_source")),
                "can_take_back_ownership": to_bool(result.get("can_take_back_ownership")),
                "buy_tax": to_float(result.get("buy_tax")),
                "sell_tax": to_float(result.get("sell_tax")),
            }
        except Exception as exc:
            logger.warning(f"GoPlus check failed for {address}: {exc}")
            return None
