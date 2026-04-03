import asyncio
from datetime import datetime, timezone
from sqlalchemy import select, delete
from app.storage.database import AsyncSessionLocal
from app.models.analysis import ProjectAnalysis
from app.services.coin_data_fetcher import fetch_coin_details
from app.core.logger import get_logger

logger = get_logger(__name__)

# Global state for tracking progress
_analysis_state = {
    "running": False,
    "total": 0,
    "completed": 0,
    "current_project": "",
    "started_at": None,
    "finished_at": None,
}


def get_analysis_status() -> dict:
    return {**_analysis_state}


async def run_full_analysis(projects: list[dict], analysis_registry) -> None:
    """Run analysis on ALL projects in batches, saving results to DB."""
    global _analysis_state

    if _analysis_state["running"]:
        logger.warning("Analysis already running, skipping")
        return

    _analysis_state.update({
        "running": True,
        "total": len(projects),
        "completed": 0,
        "current_project": "",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    })

    try:
        # Process in batches of 5 to respect rate limits
        batch_size = 5
        for i in range(0, len(projects), batch_size):
            batch = projects[i:i + batch_size]
            _analysis_state["current_project"] = batch[0].get("name", "")

            # Fetch CoinGecko details for this batch
            cg_ids = [p["id"] for p in batch if p.get("id")]
            coin_details = await fetch_coin_details(cg_ids)

            # Run all analysis modules on this batch
            results = await analysis_registry.run_all(
                projects=batch, coin_details=coin_details
            )

            # Save results to DB
            await _save_batch_results(batch, results)

            _analysis_state["completed"] = min(i + batch_size, len(projects))
            logger.info(
                f"Analysis progress: {_analysis_state['completed']}/{_analysis_state['total']}"
            )

            # Brief pause between batches
            if i + batch_size < len(projects):
                await asyncio.sleep(3)

    except Exception as exc:
        logger.error(f"Analysis failed: {exc}", exc_info=True)
    finally:
        _analysis_state["running"] = False
        _analysis_state["finished_at"] = datetime.now(timezone.utc).isoformat()


async def _save_batch_results(
    projects: list[dict], module_results: dict
) -> None:
    """Save analysis results for a batch of projects to DB."""
    # Organize results by project
    by_project: dict[str, dict] = {}
    for module_name, result in module_results.items():
        for analysis in result.data.get("analyses", []):
            pid = analysis.get("project_id")
            if pid:
                if pid not in by_project:
                    by_project[pid] = {}
                by_project[pid][module_name] = analysis

    async with AsyncSessionLocal() as session:
        for pid, modules in by_project.items():
            # Delete old analysis
            await session.execute(
                delete(ProjectAnalysis).where(ProjectAnalysis.coingecko_id == pid)
            )

            # Collect red flags from all modules
            all_flags = []
            for mod_data in modules.values():
                all_flags.extend(mod_data.get("red_flags", []))

            tok = modules.get("tokenomics_analyzer", {})
            gh = modules.get("github_analyzer", {})
            oc = modules.get("onchain_analyzer", {})
            ca = modules.get("contract_auditor", {})
            ha = modules.get("holder_analyzer", {})

            tok_score = tok.get("tokenomics_score")
            gh_score = gh.get("github_score")
            oc_score = oc.get("onchain_score")
            ca_score = ca.get("audit_score")
            ha_score = ha.get("holder_score")

            scores = [s for s in [tok_score, gh_score, oc_score, ca_score, ha_score] if s is not None]
            total = sum(scores) if scores else None

            row = ProjectAnalysis(
                coingecko_id=pid,
                tokenomics_score=tok_score,
                github_score=gh_score,
                onchain_score=oc_score,
                audit_score=ca_score,
                holder_score=ha_score,
                total_score=total,
                tokenomics_data=tok or None,
                github_data=gh or None,
                onchain_data=oc or None,
                audit_data=ca or None,
                holder_data=ha or None,
                red_flags=all_flags or None,
            )
            session.add(row)

        await session.commit()
