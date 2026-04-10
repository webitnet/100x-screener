from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)

# Weights from ТЗ (total 100 points)
CATEGORY_WEIGHTS = {
    "technology": 20,      # GitHub + contract audit
    "tokenomics": 20,      # Tokenomics analyzer
    "onchain_traction": 20, # On-chain analyzer
    "team_backing": 15,    # VC / team signals (from whale/smart money for now)
    "community": 10,       # Social momentum
    "narrative": 10,       # Narrative analyzer
    "smart_money": 5,      # Whale detector
}

CLASSIFICATIONS = [
    (80, "Strong Buy", "3-5%"),
    (65, "Buy", "2-3%"),
    (50, "Watch", "Watchlist"),
    (30, "Weak", "Only if strong narrative"),
    (0, "Avoid", "Do not invest"),
]


class ProjectScorer(BaseModule):
    name = "project_scorer"

    async def run(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        """This module is not run in the pipeline — it's used by analysis_runner
        to compute final scores from all module results."""
        return self.ok(data={}, message="Scorer is used via compute_score()")

    @staticmethod
    def compute_score(module_results: dict) -> dict:
        """Compute final weighted score from all module results.

        Args:
            module_results: dict of {module_name: analysis_dict} for one project
        """
        tok = module_results.get("tokenomics_analyzer", {})
        gh = module_results.get("github_analyzer", {})
        oc = module_results.get("onchain_analyzer", {})
        ca = module_results.get("contract_auditor", {})
        ha = module_results.get("holder_analyzer", {})
        wh = module_results.get("whale_detector", {})
        na = module_results.get("narrative_analyzer", {})
        rf = module_results.get("red_flag_detector", {})
        so = module_results.get("social_tracker", {})
        ex = module_results.get("exchange_tracker", {})

        categories = {}

        # Technology (20 pts) = GitHub + Audit average
        gh_score = gh.get("github_score", 0) or 0
        ca_score = ca.get("audit_score", 0) or 0
        categories["technology"] = min(
            round((gh_score + ca_score) / 2), 20
        )

        # Tokenomics (20 pts)
        categories["tokenomics"] = min(
            tok.get("tokenomics_score", 0) or 0, 20
        )

        # On-chain traction (20 pts)
        categories["onchain_traction"] = min(
            oc.get("onchain_score", 0) or 0, 20
        )

        # Team & Backing (15 pts) = holder + smart money + exchange
        ha_score = ha.get("holder_score", 0) or 0
        sm_raw = wh.get("smart_money_score", 0) or 0
        ex_score = ex.get("exchange_score", 0) or 0
        categories["team_backing"] = min(
            round(ha_score * 0.6 + sm_raw * 1.0 + ex_score * 0.5),
            15,
        )

        # Community & Social (10 pts)
        so_score = so.get("social_score", 0) or 0
        categories["community"] = min(so_score, 10)

        # Narrative (10 pts)
        categories["narrative"] = min(
            na.get("narrative_score", 0) or 0, 10
        )

        # Smart Money (5 pts)
        categories["smart_money"] = min(sm_raw, 5)

        # Raw total before penalties
        raw_total = sum(categories.values())

        # Penalties from red flag detector
        penalties = rf.get("total_penalty", 0) or 0

        # Final score (0-100, clamped)
        final_score = max(0, min(100, raw_total + penalties))

        # Classification
        classification = "Avoid"
        position_size = "Do not invest"
        for threshold, label, size in CLASSIFICATIONS:
            if final_score >= threshold:
                classification = label
                position_size = size
                break

        # Critical red flags force Avoid regardless of score
        if rf.get("disqualified"):
            classification = "Avoid"
            position_size = "Do not invest (critical red flag)"

        return {
            "raw_total": raw_total,
            "penalties": penalties,
            "final_score": final_score,
            "categories": categories,
            "classification": classification,
            "position_size": position_size,
        }
