from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)

# Active narratives 2025-2026 from ТЗ
NARRATIVES = {
    "AI & Crypto": {
        "keywords": ["ai", "artificial intelligence", "machine learning", "neural", "gpt", "llm",
                      "inference", "compute", "agent", "autonomous"],
        "weight": 10,
    },
    "Modular Blockchains": {
        "keywords": ["modular", "data availability", "rollup", "sequencer", "celestia", "eigen",
                      "layer 2", "l2", "optimistic", "zk rollup"],
        "weight": 8,
    },
    "RWA Tokenization": {
        "keywords": ["rwa", "real world asset", "tokenized", "real estate", "bond", "treasury",
                      "commodity", "credit", "securitize"],
        "weight": 9,
    },
    "DePIN": {
        "keywords": ["depin", "physical infrastructure", "iot", "wireless", "energy", "storage",
                      "compute network", "gpu", "bandwidth", "sensor"],
        "weight": 9,
    },
    "ZK / Privacy": {
        "keywords": ["zero knowledge", "zk", "zkp", "privacy", "private", "anonymous",
                      "confidential", "mpc", "fhe", "homomorphic"],
        "weight": 7,
    },
    "Bitcoin L2 / DeFi on Bitcoin": {
        "keywords": ["bitcoin l2", "btc layer", "ordinals", "brc-20", "stacks", "lightning",
                      "bitcoin defi", "btcfi", "runes"],
        "weight": 8,
    },
    "Restaking": {
        "keywords": ["restaking", "eigenlayer", "avs", "liquid restaking", "lrt",
                      "shared security", "ether.fi", "renzo", "puffer"],
        "weight": 7,
    },
    "Intent / Chain Abstraction": {
        "keywords": ["intent", "chain abstraction", "account abstraction", "cross-chain",
                      "interoperability", "bridge", "omnichain", "multichain"],
        "weight": 6,
    },
    "DeFi": {
        "keywords": ["defi", "decentralized finance", "dex", "lending", "yield", "amm",
                      "liquidity", "swap", "perp", "perpetual", "derivatives"],
        "weight": 6,
    },
    "Gaming / Metaverse": {
        "keywords": ["gaming", "game", "metaverse", "nft", "play to earn", "p2e",
                      "gamefi", "virtual world"],
        "weight": 5,
    },
    "Social / Creator": {
        "keywords": ["social", "socialfi", "creator", "content", "decentralized social",
                      "lens", "farcaster", "friend"],
        "weight": 5,
    },
}


class NarrativeAnalyzer(BaseModule):
    name = "narrative_analyzer"

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
            results.append(self._analyse(cg_id, detail))

        logger.info(f"Narrative: analysed {len(results)}/{len(projects)} projects")
        return self.ok(
            data={"analyses": results},
            message=f"Analysed {len(results)} projects for narrative fit",
        )

    def _analyse(self, cg_id: str, detail: dict) -> dict:
        # Collect all text to search for narrative keywords
        text_parts = [
            detail.get("name", ""),
            detail.get("description", {}).get("en", ""),
            " ".join(detail.get("categories") or []),
        ]
        text = " ".join(text_parts).lower()

        # Also check CoinGecko categories
        cg_categories = [c.lower() for c in (detail.get("categories") or [])]

        matched_narratives = []
        total_weight = 0

        for narrative, config in NARRATIVES.items():
            matched = False
            for keyword in config["keywords"]:
                if keyword in text or keyword in " ".join(cg_categories):
                    matched = True
                    break
            if matched:
                matched_narratives.append(narrative)
                total_weight += config["weight"]

        # Score (0-10 for narrative fit)
        if total_weight >= 15:
            score = 10
        elif total_weight >= 10:
            score = 8
        elif total_weight >= 6:
            score = 5
        elif total_weight > 0:
            score = 3
        else:
            score = 0

        return {
            "project_id": cg_id,
            "matched_narratives": matched_narratives,
            "narrative_weight": total_weight,
            "narrative_score": score,
            "red_flags": [],
        }
