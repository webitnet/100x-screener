from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)

# Penalty definitions from ТЗ
PENALTIES = {
    "fdv_mcap_ratio_critical": {"condition": "FDV/MCap > 10x", "penalty": -15, "severity": "critical"},
    "team_alloc_high": {"condition": "Team allocation > 30%", "penalty": -15, "severity": "critical"},
    "honeypot": {"condition": "Honeypot / mint functions", "penalty": -15, "severity": "critical"},
    "no_audit": {"condition": "No audit / not verified", "penalty": -10, "severity": "high"},
    "top10_concentrated": {"condition": "Top-10 holders > 60%", "penalty": -10, "severity": "high"},
    "anon_no_vc": {"condition": "Anonymous team + 0 VC", "penalty": -10, "severity": "high"},
    "big_unlock": {"condition": "Unlock > 20% in 3 months", "penalty": -10, "severity": "medium"},
    "github_silent": {"condition": "GitHub silent 30+ days", "penalty": -5, "severity": "medium"},
    "bot_ratio": {"condition": "Bot ratio > 40%", "penalty": -5, "severity": "medium"},
}


class RedFlagDetector(BaseModule):
    name = "red_flag_detector"

    async def run(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        if not projects:
            return self.fail("No projects to analyse")

        results = []
        for p in projects:
            cg_id = p.get("id")
            if not cg_id:
                continue
            detail = (coin_details or {}).get(cg_id)
            if not detail:
                continue
            results.append(self._detect_flags(cg_id, detail))

        logger.info(f"RedFlags: checked {len(results)}/{len(projects)} projects")
        return self.ok(
            data={"analyses": results},
            message=f"Checked {len(results)} projects for red flags",
        )

    @staticmethod
    def compute_penalties(cg_id: str, modules: dict) -> dict:
        """Compute red flags and penalties from other modules' analyses.
        Called by analysis_runner after all analyzers finish, so we can
        cross-reference holder/audit/github data."""
        tok = modules.get("tokenomics_analyzer") or {}
        ca = modules.get("contract_auditor") or {}
        ha = modules.get("holder_analyzer") or {}
        gh = modules.get("github_analyzer") or {}

        flags: list[dict] = []
        disqualified = False

        def add(msg: str, sev: str) -> None:
            flags.append({"flag": msg, "severity": sev})

        # CRITICAL → auto-disqualification (classification forced to Avoid)
        if ca.get("is_honeypot"):
            add("Honeypot detected", "critical")
            disqualified = True
        if ca.get("is_mintable"):
            add("Mint function present", "critical")
            disqualified = True
        if ca.get("is_open_source") is False:
            add("Contract not verified", "critical")
            disqualified = True

        # HIGH → display only (already penalized in category scores)
        fdv_ratio = tok.get("fdv_to_mcap")
        if fdv_ratio and fdv_ratio > 10:
            add(f"FDV/MCap = {fdv_ratio:.1f}x (>10x)", "high")
        circ_ratio = tok.get("circulating_to_total")
        if circ_ratio is not None and circ_ratio < 0.1:
            add(f"Only {circ_ratio:.0%} circulating", "high")
        top10 = ha.get("top10_holder_pct")
        if top10 is not None and top10 > 60:
            add(f"Top-10 holders own {top10:.1f}% of supply", "high")

        # MEDIUM → display only
        days = gh.get("days_since_last_push")
        if days is not None and days > 30:
            add(f"GitHub silent {days} days", "medium")
        elif not gh:
            add("No GitHub repository", "medium")

        if disqualified:
            risk_level = "critical"
        elif any(f["severity"] == "high" for f in flags):
            risk_level = "high"
        elif flags:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "project_id": cg_id,
            "red_flags": [f["flag"] for f in flags],
            "penalties": flags,
            "total_penalty": 0,
            "disqualified": disqualified,
            "risk_level": risk_level,
            "penalty_score": 0,
        }

    def _detect_flags(self, cg_id: str, detail: dict) -> dict:
        market = detail.get("market_data") or {}
        flags = []
        total_penalty = 0

        # 1. FDV/MCap > 10x
        mcap = market.get("market_cap", {}).get("usd") or 0
        fdv = market.get("fully_diluted_valuation", {}).get("usd") or 0
        if mcap > 0 and fdv > 0:
            ratio = fdv / mcap
            if ratio > 10:
                flags.append({"flag": f"FDV/MCap = {ratio:.1f}x (>10x)", "penalty": -15, "severity": "critical"})
                total_penalty -= 15

        # 2. Low circulating supply (proxy for team/locked allocation)
        circulating = market.get("circulating_supply") or 0
        total_supply = market.get("total_supply") or 0
        if total_supply > 0 and circulating > 0:
            circ_ratio = circulating / total_supply
            if circ_ratio < 0.1:
                flags.append({"flag": f"Only {circ_ratio:.0%} circulating (potential high team alloc)", "penalty": -15, "severity": "critical"})
                total_penalty -= 15
            elif circ_ratio < 0.3:
                flags.append({"flag": f"Low circulation: {circ_ratio:.0%}", "penalty": -5, "severity": "medium"})
                total_penalty -= 5

        # 3. No GitHub / inactive development
        repos = detail.get("links", {}).get("repos_url", {}).get("github", [])
        if not repos:
            flags.append({"flag": "No GitHub repository", "penalty": -5, "severity": "medium"})
            total_penalty -= 5

        # 4. No homepage / suspicious links
        homepage = detail.get("links", {}).get("homepage", [])
        has_homepage = any(url for url in homepage if url)
        if not has_homepage:
            flags.append({"flag": "No project website", "penalty": -5, "severity": "medium"})
            total_penalty -= 5

        # 5. Very low community
        twitter = detail.get("links", {}).get("twitter_screen_name")
        telegram = detail.get("links", {}).get("telegram_channel_identifier")
        if not twitter and not telegram:
            flags.append({"flag": "No Twitter or Telegram", "penalty": -5, "severity": "medium"})
            total_penalty -= 5

        # 6. Extreme price volatility (potential pump & dump)
        price_change_24h = market.get("price_change_percentage_24h") or 0
        if price_change_24h > 100:
            flags.append({"flag": f"Price surged +{price_change_24h:.0f}% in 24h (pump risk)", "penalty": -5, "severity": "medium"})
            total_penalty -= 5
        elif price_change_24h < -50:
            flags.append({"flag": f"Price crashed {price_change_24h:.0f}% in 24h (dump)", "penalty": -10, "severity": "high"})
            total_penalty -= 10

        # Classification based on penalty
        if total_penalty <= -30:
            risk_level = "critical"
        elif total_penalty <= -15:
            risk_level = "high"
        elif total_penalty <= -5:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "project_id": cg_id,
            "red_flags": [f["flag"] for f in flags],
            "penalties": flags,
            "total_penalty": total_penalty,
            "risk_level": risk_level,
            "penalty_score": total_penalty,  # negative number, added to total score
        }
