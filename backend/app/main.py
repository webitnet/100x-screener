from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.storage.database import init_db
import app.models.analysis  # register ProjectAnalysis model
from app.core.module_registry import ModuleRegistry, registry
from app.modules.discovery.coingecko_scanner import CoinGeckoScanner
from app.modules.discovery.dexscreener_scanner import DexScreenerScanner
from app.modules.analysis.tokenomics_analyzer import TokenomicsAnalyzer
from app.modules.analysis.github_analyzer import GitHubAnalyzer
from app.modules.analysis.onchain_analyzer import OnChainAnalyzer
from app.modules.analysis.contract_auditor import ContractAuditor
from app.modules.analysis.holder_analyzer import HolderAnalyzer
from app.modules.signals.whale_detector import WhaleDetector
from app.modules.signals.red_flag_detector import RedFlagDetector
from app.modules.signals.narrative_analyzer import NarrativeAnalyzer
from app.modules.signals.social_tracker import SocialTracker
from app.modules.signals.exchange_tracker import ExchangeTracker
import app.models.alert  # register Alert model
import app.models.watchlist  # register Watchlist models
from app.core.scheduler import init_scheduler, shutdown_scheduler
from app.api.routes import router

# Separate registries for pipeline stages
discovery_registry = ModuleRegistry()
analysis_registry = ModuleRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Discovery modules
    discovery_registry.register(CoinGeckoScanner())
    discovery_registry.register(DexScreenerScanner())

    # Analysis modules (Stage 2)
    analysis_registry.register(TokenomicsAnalyzer())
    analysis_registry.register(GitHubAnalyzer())
    analysis_registry.register(OnChainAnalyzer())
    analysis_registry.register(ContractAuditor())
    analysis_registry.register(HolderAnalyzer())

    # Signal modules (Stage 3)
    analysis_registry.register(WhaleDetector())
    analysis_registry.register(RedFlagDetector())
    analysis_registry.register(NarrativeAnalyzer())

    # Stage 4 modules
    analysis_registry.register(SocialTracker())
    analysis_registry.register(ExchangeTracker())

    # Start scheduler
    init_scheduler(discovery_registry, analysis_registry)
    yield
    shutdown_scheduler()


app = FastAPI(title="100x Crypto Screener", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")
