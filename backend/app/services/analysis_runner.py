import asyncio
from datetime import datetime, timezone
from sqlalchemy import delete
from app.storage.database import AsyncSessionLocal
from app.models.analysis import ProjectAnalysis
from app.services.coin_data_fetcher import fetch_coin_details
from app.services.alert_service import check_and_create_alerts
from app.services.watchlist_service import record_score
from app.modules.scoring.project_scorer import ProjectScorer
from app.core.logger import get_logger

logger = get_logger(__name__)

# Global state for tracking progress
_analysis_state = {
    "running": False,
    "total": 0,
    "completed": 0,
    "analysed": 0,
    "failed": 0,
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

    # Reorder: CoinGecko projects first (reliable), dex- projects last (may not exist)
    cg_first = [p for p in projects if not p.get("id", "").startswith("dex-")]
    dex_last = [p for p in projects if p.get("id", "").startswith("dex-")]
    projects = cg_first + dex_last
    logger.info(f"Analysis order: {len(cg_first)} CoinGecko + {len(dex_last)} DexScreener projects")

    _analysis_state.update({
        "running": True,
        "total": len(projects),
        "completed": 0,
        "analysed": 0,
        "failed": 0,
        "current_project": "",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    })

    try:
        batch_size = 3  # smaller batches to stay within rate limits
        for i in range(0, len(projects), batch_size):
            batch = projects[i:i + batch_size]
            _analysis_state["current_project"] = batch[0].get("name", "")

            try:
                cg_ids = [p["id"] for p in batch if p.get("id")]
                coin_details = await fetch_coin_details(cg_ids, projects=batch)

                fetched = len(coin_details)
                batch_failed = len(cg_ids) - fetched

                if coin_details:
                    results = await analysis_registry.run_all(
                        projects=batch, coin_details=coin_details
                    )
                    await _save_batch_results(batch, results)
                    _analysis_state["analysed"] += fetched
                else:
                    logger.warning(
                        f"Batch {i//batch_size + 1}: no data fetched, skipping analysis"
                    )

                _analysis_state["failed"] += batch_failed
            except Exception as batch_exc:
                logger.error(
                    f"Batch {i//batch_size + 1} failed: {batch_exc}",
                    exc_info=True,
                )
                _analysis_state["failed"] += len(batch)

            _analysis_state["completed"] = min(
                i + batch_size, len(projects)
            )
            logger.info(
                f"Analysis progress: "
                f"{_analysis_state['completed']}/"
                f"{_analysis_state['total']} "
                f"(analysed: {_analysis_state['analysed']}, "
                f"failed: {_analysis_state['failed']})"
            )

            if i + batch_size < len(projects):
                # Longer pause between batches for rate limit
                await asyncio.sleep(15)

    except Exception as exc:
        logger.error(f"Analysis failed: {exc}", exc_info=True)
    finally:
        _analysis_state["running"] = False
        _analysis_state["finished_at"] = (
            datetime.now(timezone.utc).isoformat()
        )


async def _save_batch_results(
    projects: list[dict], module_results: dict
) -> None:
    """Save analysis results for a batch of projects to DB."""
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
            await session.execute(
                delete(ProjectAnalysis).where(ProjectAnalysis.coingecko_id == pid)
            )

            # Collect red flags from all modules
            all_flags = []
            for mod_data in modules.values():
                all_flags.extend(mod_data.get("red_flags", []))

            # Stage 2 scores
            tok = modules.get("tokenomics_analyzer", {})
            gh = modules.get("github_analyzer", {})
            oc = modules.get("onchain_analyzer", {})
            ca = modules.get("contract_auditor", {})
            ha = modules.get("holder_analyzer", {})

            # Stage 3 scores
            wh = modules.get("whale_detector", {})
            rf = modules.get("red_flag_detector", {})
            na = modules.get("narrative_analyzer", {})

            # Stage 4 scores
            so = modules.get("social_tracker", {})
            ex = modules.get("exchange_tracker", {})

            tok_score = tok.get("tokenomics_score")
            gh_score = gh.get("github_score")
            oc_score = oc.get("onchain_score")
            ca_score = ca.get("audit_score")
            ha_score = ha.get("holder_score")
            sm_score = wh.get("smart_money_score")
            na_score = na.get("narrative_score")
            so_score = so.get("social_score")
            ex_score = ex.get("exchange_score")
            penalty = rf.get("total_penalty") or 0

            # Also add red flag detector flags
            all_flags.extend(rf.get("red_flags", []))
            # Deduplicate flags
            all_flags = list(dict.fromkeys(all_flags))

            # Use ProjectScorer for weighted total
            scorer_input = {
                "tokenomics_analyzer": tok,
                "github_analyzer": gh,
                "onchain_analyzer": oc,
                "contract_auditor": ca,
                "holder_analyzer": ha,
                "whale_detector": wh,
                "narrative_analyzer": na,
                "red_flag_detector": rf,
                "social_tracker": so,
                "exchange_tracker": ex,
            }
            scored = ProjectScorer.compute_score(scorer_input)
            total = scored["final_score"]

            row = ProjectAnalysis(
                coingecko_id=pid,
                tokenomics_score=tok_score,
                github_score=gh_score,
                onchain_score=oc_score,
                audit_score=ca_score,
                holder_score=ha_score,
                smart_money_score=sm_score,
                narrative_score=na_score,
                social_score=so_score,
                exchange_score=ex_score,
                penalty_score=penalty,
                total_score=total,
                tokenomics_data=tok or None,
                github_data=gh or None,
                onchain_data=oc or None,
                audit_data=ca or None,
                holder_data=ha or None,
                whale_data=wh or None,
                narrative_data=na or None,
                red_flag_data=rf or None,
                social_data=so or None,
                exchange_data=ex or None,
                red_flags=all_flags or None,
                risk_level=rf.get("risk_level"),
            )
            session.add(row)

            # Find project name for alerts
            pname = pid
            for proj in projects:
                if proj.get("id") == pid:
                    pname = proj.get("name", pid)
                    break

            # Create alerts for notable events
            await check_and_create_alerts(
                session=session,
                coingecko_id=pid,
                project_name=pname,
                score=total,
                classification=scored["classification"],
                red_flags=all_flags,
                whale_signals=wh.get("whale_signals", []),
                exchange_signals=ex.get(
                    "exchange_signals", []
                ),
            )

            # Record score history for trend tracking
            await record_score(
                session,
                coingecko_id=pid,
                total_score=total,
                categories=scored.get("categories"),
            )

        await session.commit()
