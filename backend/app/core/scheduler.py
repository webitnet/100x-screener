"""APScheduler-based scheduler for automated discovery and analysis runs."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.storage.database import AsyncSessionLocal
from app.services.project_service import upsert_projects, get_cached_projects
from app.core.result_aggregator import ResultAggregator
from app.services.analysis_runner import run_full_analysis, get_analysis_status
from app.core.logger import get_logger

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()
aggregator = ResultAggregator()

# Will be set from main.py at startup
_discovery_registry = None
_analysis_registry = None


def init_scheduler(discovery_registry, analysis_registry):
    global _discovery_registry, _analysis_registry
    _discovery_registry = discovery_registry
    _analysis_registry = analysis_registry

    # Discovery every 6 hours
    scheduler.add_job(
        scheduled_discovery,
        IntervalTrigger(hours=6),
        id="discovery_scan",
        name="Discovery Scan (every 6h)",
        replace_existing=True,
    )

    # Analysis every 6 hours, offset by 10 min after discovery
    scheduler.add_job(
        scheduled_analysis,
        IntervalTrigger(hours=6, minutes=10),
        id="full_analysis",
        name="Full Analysis (every 6h)",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started: discovery every 6h, analysis every 6h10m")


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def scheduled_discovery():
    """Run discovery scan automatically."""
    logger.info("[Scheduler] Starting discovery scan...")
    try:
        results = await _discovery_registry.run_all()
        summary = aggregator.aggregate(results)
        projects = summary.get("projects", [])

        async with AsyncSessionLocal() as session:
            saved = await upsert_projects(session, projects)

        logger.info(
            f"[Scheduler] Discovery complete: "
            f"{len(projects)} found, {saved} saved"
        )
    except Exception as e:
        logger.error(f"[Scheduler] Discovery failed: {e}", exc_info=True)


async def scheduled_analysis():
    """Run full analysis on all discovered projects."""
    status = get_analysis_status()
    if status["running"]:
        logger.warning("[Scheduler] Analysis already running, skipping")
        return

    logger.info("[Scheduler] Starting full analysis...")
    try:
        async with AsyncSessionLocal() as session:
            projects = await get_cached_projects(session)

        if not projects:
            logger.warning("[Scheduler] No projects to analyse")
            return

        await run_full_analysis(projects, _analysis_registry)
        logger.info(
            f"[Scheduler] Analysis complete: {len(projects)} projects"
        )
    except Exception as e:
        logger.error(f"[Scheduler] Analysis failed: {e}", exc_info=True)


def get_scheduler_status() -> dict:
    """Return info about scheduled jobs."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat()
            if job.next_run_time else None,
        })
    return {
        "running": scheduler.running,
        "jobs": jobs,
    }
