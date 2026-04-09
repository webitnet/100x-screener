import asyncio
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.module_registry import registry
from app.core.result_aggregator import aggregator
from app.storage.database import get_db
from app.models.project import Project
from app.models.analysis import ProjectAnalysis
from app.services.project_service import upsert_projects, is_cache_fresh, get_cached_projects
from app.services.analysis_runner import run_full_analysis, get_analysis_status
from app.services.alert_service import get_recent_alerts
from app.services.watchlist_service import (
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
)
from app.core.scheduler import get_scheduler_status

router = APIRouter()


def _get_discovery_registry():
    from app.main import discovery_registry
    return discovery_registry


def _get_analysis_registry():
    from app.main import analysis_registry
    return analysis_registry


@router.get("/health")
async def health():
    discovery = _get_discovery_registry()
    analysis = _get_analysis_registry()
    return {
        "status": "ok",
        "discovery_modules": discovery.list_names(),
        "analysis_modules": analysis.list_names(),
    }


@router.get("/modules")
async def list_modules():
    discovery = _get_discovery_registry()
    analysis = _get_analysis_registry()
    return {
        "discovery": discovery.list_names(),
        "analysis": analysis.list_names(),
    }


@router.post("/scan")
async def run_scan(
    force: bool = Query(False, description="Force fresh scan ignoring cache"),
    db: AsyncSession = Depends(get_db),
):
    """Run discovery scan — find new projects matching filters."""
    discovery = _get_discovery_registry()

    if not force and await is_cache_fresh(db):
        projects = await get_cached_projects(db)
        return {
            "total_modules": len(discovery.list_names()),
            "successful": len(discovery.list_names()),
            "failed": 0,
            "warnings": 0,
            "failed_modules": [],
            "projects": projects,
            "saved_to_db": len(projects),
            "from_cache": True,
        }

    results = await discovery.run_all()
    summary = aggregator.aggregate(results)
    saved = await upsert_projects(db, summary["projects"])
    summary["saved_to_db"] = saved
    summary["from_cache"] = False
    return summary


@router.post("/analyse")
async def run_analysis(
    limit: int = Query(0, description="Max projects (0 = all)"),
    db: AsyncSession = Depends(get_db),
):
    """Start background analysis of all discovered projects."""
    analysis = _get_analysis_registry()

    status = get_analysis_status()
    if status["running"]:
        return {"message": "Analysis already running", **status}

    projects = await get_cached_projects(db)
    if not projects:
        return {"error": "No projects found. Run /scan first."}

    if limit > 0:
        projects = projects[:limit]

    # Run in background
    asyncio.create_task(run_full_analysis(projects, analysis))

    return {
        "message": f"Analysis started for {len(projects)} projects",
        "total": len(projects),
    }


@router.get("/analyse/status")
async def analysis_status():
    """Get current analysis progress."""
    return get_analysis_status()


@router.get("/analyse/results")
async def analysis_results(db: AsyncSession = Depends(get_db)):
    """Get all stored analysis results."""
    result = await db.execute(
        select(ProjectAnalysis).order_by(ProjectAnalysis.total_score.desc())
    )
    analyses = result.scalars().all()

    return {
        "count": len(analyses),
        "results": [
            {
                "coingecko_id": a.coingecko_id,
                "total_score": a.total_score,
                "tokenomics_score": a.tokenomics_score,
                "github_score": a.github_score,
                "onchain_score": a.onchain_score,
                "audit_score": a.audit_score,
                "holder_score": a.holder_score,
                "smart_money_score": a.smart_money_score,
                "narrative_score": a.narrative_score,
                "penalty_score": a.penalty_score,
                "risk_level": a.risk_level,
                "red_flags": a.red_flags or [],
                "tokenomics_data": a.tokenomics_data,
                "github_data": a.github_data,
                "onchain_data": a.onchain_data,
                "audit_data": a.audit_data,
                "holder_data": a.holder_data,
                "whale_data": a.whale_data,
                "social_score": a.social_score,
                "exchange_score": a.exchange_score,
                "narrative_data": a.narrative_data,
                "red_flag_data": a.red_flag_data,
                "social_data": a.social_data,
                "exchange_data": a.exchange_data,
                "analysed_at": a.analysed_at.isoformat() if a.analysed_at else None,
            }
            for a in analyses
        ],
    }


@router.post("/scan/{module_name}")
async def run_module(module_name: str):
    result = await registry.run_one(module_name)
    return result


@router.get("/projects")
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project).order_by(Project.market_cap.asc())
    )
    projects = result.scalars().all()
    return {
        "count": len(projects),
        "projects": [
            {
                "id": p.id,
                "coingecko_id": p.coingecko_id,
                "name": p.name,
                "ticker": p.ticker,
                "chain": p.chain,
                "market_cap": p.market_cap,
                "volume_24h": p.volume_24h,
                "price": p.price,
                "age_days": p.age_days,
                "discovered_at": (
                    p.discovered_at.isoformat()
                    if p.discovered_at else None
                ),
            }
            for p in projects
        ],
    }


@router.get("/alerts")
async def list_alerts(
    limit: int = Query(50, description="Max alerts to return"),
):
    """Get recent alerts."""
    alerts = await get_recent_alerts(limit=limit)
    return {"count": len(alerts), "alerts": alerts}


# --- Watchlist ---

@router.get("/watchlist")
async def watchlist_list(db: AsyncSession = Depends(get_db)):
    """Get all watchlist items with score history."""
    items = await get_watchlist(db)
    return {"count": len(items), "items": items}


@router.post("/watchlist/{coingecko_id}")
async def watchlist_add(
    coingecko_id: str,
    name: str = Query("", description="Project name"),
    ticker: str = Query("", description="Ticker"),
    notes: str = Query(None, description="Notes"),
    db: AsyncSession = Depends(get_db),
):
    """Add a project to the watchlist."""
    item = await add_to_watchlist(
        db, coingecko_id, name or coingecko_id, ticker, notes
    )
    return {
        "message": f"Added {coingecko_id} to watchlist",
        "coingecko_id": item.coingecko_id,
    }


@router.delete("/watchlist/{coingecko_id}")
async def watchlist_remove(
    coingecko_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove a project from the watchlist."""
    removed = await remove_from_watchlist(db, coingecko_id)
    if not removed:
        return {"message": f"{coingecko_id} not in watchlist"}
    return {"message": f"Removed {coingecko_id} from watchlist"}


# --- Scheduler ---

@router.get("/scheduler")
async def scheduler_status():
    """Get scheduler status and next run times."""
    return get_scheduler_status()
