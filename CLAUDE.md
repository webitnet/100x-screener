# 100x Crypto Screener — Project Instructions for Claude Code

> This file contains the full technical specification (ТЗ) for the 100x Crypto Screener project.
> Claude Code must read this file at the start of every session and strictly follow all rules below.

---

## Role

Act as a **senior full-stack engineer**, Python architect, crypto research systems designer, and data pipeline engineer.

---

## Project Goal

Build a modular web system for automated discovery, analysis, and scoring of early-stage crypto projects with 100x+ growth potential. The system must:

- Run independent data collection modules and retrieve their results
- Process and aggregate module data into a unified score
- Display each module's status in real time
- Continue working even if a module fails (fault tolerance)
- Notify the user about broken modules
- Allow easy addition, disabling, modification, or removal of modules
- Automatically run scans on a schedule (scheduler)
- Send alerts (Telegram / email) when high-score projects are found

---

## Key Development Rules

- **Work strictly step by step.** Create only one stage or module at a time.
- **Each stage must be completed and tested before moving on.** Do not proceed until the current stage is done.
- **Do not generate the entire project at once.** Do not mix multiple large stages in one step.
- **Each module must be autonomous and independent.** No module should directly depend on another.
- **If a module fails, the system must:** log the error; show the user the problem; continue working; process results from other modules; not crash completely.
- **Code must be:** readable; scalable; understandable; easy to swap modules; suitable for future testing.
- **Keep CLAUDE.md up to date.** This file is the only persistent project context across sessions. Whenever we make a decision that changes architecture, scoring logic, data model, module contracts, or development stage status, proactively propose updating the relevant section of CLAUDE.md so future sessions start with accurate information. Do not write ephemeral changelogs here — record durable facts (rules, rationale, current stage), not task history (git log is authoritative for that).

---

## System Architecture

### 5 Layers

| Layer | Description |
|-------|-------------|
| Core | Runs modules, collects results, checks statuses, aggregates, passes to frontend, stays operational during partial failures |
| Independent Modules | 19 modules in 5 groups: Discovery, Analysis, Signals, Risk, Scoring |
| Processing & Aggregation Layer | Redis queue + result aggregator + caching |
| Scheduler | APScheduler / Celery Beat: automatic module runs on schedule |
| Frontend | Dashboard, project cards, scoring, alerts, module statuses |

### Tech Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Backend | FastAPI (Python 3.11+) | Async, fast, ideal for data pipelines |
| Frontend | React 18 + Next.js 14 | SSR, fast UI, large ecosystem |
| DB (production) | PostgreSQL + asyncpg | Concurrent writes, JSONB, reliability |
| DB (dev/test) | SQLite | Fast start without infrastructure |
| Cache / Queue | Redis | API caching (TTL), Celery message broker |
| Task Queue | Celery + Redis | Async module runs, retry logic |
| ORM | SQLAlchemy 2.0 (async) | Typed models, migrations (Alembic) |
| Exchange Format | JSON | Universal standard |
| Alerts | Telegram Bot API + SMTP | Instant notifications |

### Core Rules

The core must:
- Run modules in parallel (via asyncio / Celery tasks)
- Receive results in standard JSON format
- Check each module's status (success / error / warning / timeout)
- Aggregate successful results and pass them to the scoring engine
- Report errors but NOT crash due to a single module failure

---

## Screening Pipeline: 8 Stages

### Stage 1 — Discovery
**Goal:** Find new projects that meet basic criteria.
**Schedule:** Every 6 hours automatically.

**Data Sources:**

| Source | What We Collect |
|--------|-----------------|
| CoinGecko API | New tokens, market cap, volume, price change |
| DexScreener API | New DEX pairs, liquidity, volume spikes, trending tokens |
| DexTools API | Additional DEX metrics, DEXT Score |
| VC / Fundraising | Crunchbase, Messari, DeFiLlama raises — who invested |
| GitHub | New repositories, commit activity |
| On-chain (Etherscan+) | New contracts, holder growth |

**Pass Filters:**

| Criterion | Threshold | Notes |
|-----------|-----------|-------|
| Market cap | < $50M (optimally $1M–$20M) | Hard filter in CoinGecko scanner |
| Volume / MCap ratio | > 10% | Hard filter in CoinGecko scanner |
| Liquidity (DEX) | > $10K in pool | DexScreener scanner (not CoinGecko) |
| Network | Ethereum, Solana, Base, Arbitrum, BNB Chain | Not filterable via CoinGecko markets API |

> **Note:** Project age is NOT used as a filter. CoinGecko `/coins/markets` does not return a reliable age field (`atl_date` and `ath_date` are unrelated to project creation). Age can only be obtained via `/coins/{id}` (1 request per token), which is too expensive at discovery stage.

---

### Stage 2 — Deep Analysis
**Goal:** Full project breakdown across multiple dimensions.
**Trigger:** Project passed Discovery filters.

| Sub-module | Metrics |
|------------|---------|
| Tokenomics Analyzer | FDV, FDV/MCap ratio, circulating/total supply, vesting schedule, cliff periods, emission curve, team/advisor allocation |
| On-Chain Analyzer | Active users (DAU/WAU), TVL and its trend (week-over-week), txns/day, holder growth |
| GitHub Analyzer | Commits/week, contributors count, last commit recency, stars, forks |
| Contract Auditor | TokenSniffer score, CertiK/Hacken audit, rugcheck.xyz, honeypot/mint/blacklist function checks |
| Holder Distribution | Top-10/50/100 holders % supply, separating exchange wallets from real ones, insider wallet concentration |

---

### Stage 3 — Smart Money & VC Tracking
**Goal:** Detect accumulation by institutional investors and successful traders. This is the strongest early signal for 100x.

| Sub-module | Details |
|------------|---------|
| Whale Detector | Large transactions (source: Whale Alert, Etherscan), CEX outflows |
| Smart Money Tracker | Nansen / Arkham Intelligence: monitoring VC fund wallets (a16z, Paradigm, Polychain, Multicoin), successful traders, institutional players |
| VC Fundraising | Crunchbase / Messari / DeFiLlama Raises: who invested, how much, Tier-1 vs no-name, round valuation |

---

### Stage 4 — Narrative & Sector Analysis
**Goal:** Determine if the project aligns with current or upcoming market narratives.

**Active Narratives 2025–2026:**
- AI & Crypto (AI agents, decentralized compute, inference networks)
- Modular Blockchains (data availability, shared sequencers, rollup infra)
- RWA Tokenization (real estate, bonds, credit, commodities on-chain)
- DePIN (decentralized physical infrastructure: IoT, wireless, energy, storage)
- ZK / Privacy (zero-knowledge proofs, private DeFi, identity)
- Bitcoin L2 / DeFi on Bitcoin (staking, rollups, smart contracts on BTC)
- Restaking / EigenLayer ecosystem (AVS, liquid restaking tokens)
- Intent-based Architecture / Chain Abstraction

**Sources:** Crypto Twitter sentiment parsing, Dune dashboards by sector, Google Trends, CoinGecko categories API, DeFiLlama categories TVL.

---

### Stage 5 — Social Momentum
**Goal:** Measure social activity dynamics (growth, not static).

| Metric | Details |
|--------|---------|
| Twitter / X | Follower growth %, engagement rate, organic vs bot ratio |
| Telegram | Group size, message activity, 7/30-day growth |
| Discord | Member count growth, channel activity, developer engagement |
| Combined Score | LunarCrush Galaxy Score, Santiment Social Volume |

---

### Stage 6 — Red Flag Detection
**Goal:** Automatically detect danger signs, fraud, or weak fundamentals.

| Red Flag | Description | Severity |
|----------|-------------|----------|
| FDV/MCap > 10x | 90%+ tokens not yet on market — high dilution risk | Critical |
| Team alloc > 30% | Excessive concentration with team | Critical |
| No audit | Contract not verified or audit failed | High |
| Top-10 holders > 60% | Centralized supply = rug risk | High |
| Anonymous team + 0 VC | No reputational backing | High |
| Unlock > 20% / 3 months | Large upcoming unlock pressures price | Medium |
| GitHub silent 30+ days | Development stopped | Medium |
| Bot ratio > 40% | Fake social activity | Medium |
| Honeypot / mint functions | Contract can block selling or mint new tokens | Critical |

---

### Stage 7 — Exchange Listing Tracking
**Goal:** Track potential listings on top exchanges, which are growth catalysts ("Coinbase Effect" +90%, Binance +20–80%).

- Monitor Binance / Coinbase / Kraken announcements
- New pairs on top-20 CEX
- Track projects on Binance Launchpool / Coinbase Earn

---

### Stage 8 — Risk Management
**Goal:** Automatically calculate position size and exit levels.

| Parameter | Value |
|-----------|-------|
| Max position per project | 2–5% portfolio (depends on score) |
| Stop-loss | 5–20% (depends on volatility) |
| Take-profit strategy | Ladder: 25% at 10x, 25% at 25x, 25% at 50x, 25% at 100x |
| Max simultaneous projects | 10–15 (diversification) |

---

## Scoring System

### Main Categories (100 points)

| Category | Weight | Metrics |
|----------|--------|---------|
| Technology & Product | 20 | Mainnet vs testnet, GitHub activity, technology uniqueness, contract audit |
| Tokenomics | 20 | FDV/MCap < 5x, vesting, emission, circulating/total, team < 20% |
| On-Chain Traction | 20 | DAU/WAU growth, TVL trend (WoW), txns/day, holder count growth |
| Team & Backing | 15 | Doxxed team, Tier-1 VC, previous successful projects, advisors |
| Community & Social | 10 | Twitter growth %, Discord/Telegram activity, organic vs bot |
| Narrative Fit | 10 | Alignment with current/future trends (AI, modular, RWA, DePIN, ZK) |
| Smart Money Signal | 5 | VC/whale accumulation via Nansen/Arkham |

### Red Flag Model (no double-counting)

Red flags are **not** subtracted from the score as generic penalties. Instead:

1. **Raw score = sum of weighted categories.** Each analyzer already reduces its own category score when data looks bad (e.g. `tokenomics_analyzer` lowers `tokenomics_score` for FDV/MCap > 10x). An additional penalty on top would double-count the same fact.
2. **Red flags are classified into three severities** and handled differently:

| Severity | Examples | Effect on score | Effect on classification |
|----------|----------|-----------------|--------------------------|
| **Critical** | Honeypot, mint function, contract not verified | None (score untouched) | **Force classification = Avoid** regardless of raw score. One critical flag disqualifies the project. |
| **High** | FDV/MCap > 10x, circulation < 10%, Top-10 holders > 60% | None (already reflected in category scores) | None — displayed on the card as a warning |
| **Medium** | GitHub silent 30+ days, no GitHub repository | None (already reflected in category scores) | None — displayed on the card as a warning |

**Rationale:** red flags are asymmetric risk signals, not linear score adjustments. A honeypot token with otherwise perfect tokenomics is not "slightly worse" — it is uninvestable. High/medium flags are already visible via reduced category scores (a repo with no commits gets `github_score ≈ 0`), so subtracting extra points would punish the same metric twice.

`red_flag_detector.total_penalty` is kept at 0 for backwards compatibility and is no longer used by `ProjectScorer`. The scorer reads `red_flag_detector.disqualified` to decide whether to force `Avoid`.

### Classification

| Score | Class | Action |
|-------|-------|--------|
| 80–100 | Strong Buy | Position 3–5% portfolio |
| 65–79 | Buy | Position 2–3% portfolio |
| 50–64 | Watch | Add to watchlist, wait for improvement |
| 30–49 | Weak | Only if narrative is very strong |
| < 30 | Avoid | Do not invest |

---

## Data Model Extensions

### `ProjectAnalysis` (latest snapshot per project)
Holds the most recent analysis. Overwritten on each `Analyse All` run (DELETE + INSERT in `_save_batch_results`). Includes per-module scores, raw module JSON, plus the weighted final score: `final_score`, `classification`, `position_size`, `score_categories`.

### `ProjectAnalysisHistory` (append-only audit trail)
Lightweight snapshot inserted on every analysis run, never deleted. Powers the per-project History modal and trend/diff views. Stores: `final_score`, `classification`, `score_categories`, `red_flags`, `risk_level`, plus key metrics for diffing (`market_cap`, `fdv`, `top10_holder_pct`, `holder_count`, `commits_last_month`, `tvl_usd`).

Endpoint: `GET /analyse/history/{coingecko_id}?limit=20` returns snapshots newest-first.

## Module Implementation Details

### CoinGecko Scanner (`backend/app/modules/discovery/coingecko_scanner.py`)

**API:** `GET /api/v3/coins/markets` (free tier, ~30 req/min)

**Pagination:** Pages 2–20 (19 pages × 250 tokens = ranks ~251–5000, ~4750 tokens scanned). Page 1 skipped (top-250 are large-cap). 2-second delay between requests to respect rate limits. Stops early on HTTP 429 or empty response.

**Filters applied (only 2):**
- `market_cap > 0 AND market_cap <= $50M`
- `volume_24h / market_cap >= 10%`

**Output per project:** `id`, `name`, `ticker`, `price`, `market_cap`, `volume_24h`, `volume_to_mcap_ratio`, `price_change_24h`, `image`, `source="coingecko"`. `age_days` is always `None`.

**What the markets API does NOT provide:** chain/network, genesis date, GitHub/website links, contract addresses, detailed tokenomics. These require `/coins/{id}` (1 req per token) and are fetched later by analysis modules, not during discovery.

**Scan duration:** ~40 seconds minimum (19 pages × 2s delay). May be shorter if rate-limited.

---

## Frontend UX Conventions

### Active analysis session
While `analysis_state.running` is true, the frontend tracks `sessionStartedAt` (from `status.started_at`). Each project card has an `isStale` flag = `analysed_at_ts < sessionStartedAt`. Stale cards render at `opacity-50` and sort below fresh ones. As the runner overwrites a project's row, its timestamp jumps past `sessionStartedAt` and the card becomes fresh + reorders to the top of its score band. When `running` becomes false, `sessionStartedAt` is cleared and all cards become "fresh" again until the next session.

Projects that have never been analysed (`analysed_at_ts == null`) are NOT marked stale — they are pending.

### History modal
`ProjectCard` exposes a "History" button that opens `HistoryModal`, which fetches `/analyse/history/{id}` and shows:
- SVG sparkline of `final_score` across all snapshots
- Diff vs previous run: score, MCap, FDV, holders, top-10%, commits — green for improvements, red for regressions (Top-10% is inverted: lower is better)
- Added (`+`) and resolved (`−`) red flags between the two latest runs
- Full snapshot list with timestamps

## Project Structure

```
100x-screener/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── module_interface.py     # Base module interface
│   │   │   ├── module_registry.py     # Module registry
│   │   │   ├── result_aggregator.py   # Aggregation
│   │   │   ├── scheduler.py           # APScheduler
│   │   │   └── logger.py
│   │   ├── modules/
│   │   │   ├── discovery/             # CoinGecko, DexScreener, DexTools, VC tracker
│   │   │   ├── analysis/              # Tokenomics, on-chain, GitHub, contract audit, holder dist.
│   │   │   ├── signals/               # Whale, smart money, narrative, social, exchange listing
│   │   │   ├── risk/                  # Red flag detector, position sizer
│   │   │   └── scoring/               # Project ranker
│   │   ├── api/                   # FastAPI routes + services
│   │   ├── storage/               # database.py (SQLAlchemy), cache.py (Redis)
│   │   └── models/                # Pydantic / SQLAlchemy models
│   ├── requirements.txt
│   └── tests/
├── frontend/
│   ├── components/            # Dashboard, ProjectCard, ScoreRadar, ModuleStatus, AlertFeed
│   ├── pages/
│   └── package.json
├── docker-compose.yml         # PostgreSQL + Redis + backend + frontend
└── README.md
```

---

## API & Data Sources

### Free Tier

| Tool | Purpose | Limit |
|------|---------|-------|
| CoinGecko API | Prices, MCap, volume, token info | 10–30 req/min |
| DexScreener API | DEX pairs, trending, volume | Rate limited |
| DefiLlama API | TVL, protocol data, yields, raises | No limit (open-source) |
| GitHub API | Repository activity, commits | 5000 req/hr (auth) |
| Etherscan / BSCScan | Contract code, holders, txns | 5 req/sec |
| TokenSniffer | Audit scores, scam detection | Limited |
| CryptoCompare | Historical prices, social stats | 100K calls/mo |
| Whale Alert (free) | Large transactions | 10 req/min |

### Paid (Recommended)

| Tool | Purpose | Price |
|------|---------|-------|
| Nansen | Smart money, wallet labels, 500M+ wallets | from $100/mo |
| Arkham Intelligence | Entity identification, institutional wallets | from $0 (basic) |
| Dune Analytics | Custom on-chain SQL queries | from $0 (community) |
| Santiment | Social/on-chain analytics | from $49/mo |
| LunarCrush | Social momentum, Galaxy Score | from $0 (basic) |

### Redis Cache TTL Strategy

| Data Type | TTL | Example |
|-----------|-----|---------|
| Prices, volume | 5 min | CoinGecko price, DexScreener volume |
| Token metadata | 1 hr | Token info, contract address |
| Static data | 24 hr | Team info, audit reports, VC rounds |
| GitHub stats | 6 hr | Commits, stars, contributors |
| Scoring results | 1 hr | Final project score |

---

## Data Format (JSON)

### Module Response (standard wrapper)

```json
{
  "module_name": "coingecko_scanner",
  "status": "success",
  "message": "Scan completed",
  "data": {},
  "warnings": [],
  "updated_at": "2026-04-02T12:00:00Z"
}
```

### Final Project Scoring

```json
{
  "project": "ExampleToken",
  "ticker": "EXT",
  "chain": "ethereum",
  "market_cap": 8500000,
  "score": {
    "total": 78,
    "technology": 16,
    "tokenomics": 18,
    "onchain_traction": 14,
    "team_backing": 12,
    "community": 8,
    "narrative": 8,
    "smart_money": 4,
    "penalties": -2
  },
  "classification": "Buy",
  "position_size": "2-3%",
  "red_flags": ["No GitHub activity 15 days"],
  "updated_at": "2026-04-02T12:00:00Z"
}
```

---

## Frontend Requirements

| Component | Description |
|-----------|-------------|
| Dashboard | Main screen: top projects by score, filters by category/network/narrative |
| ProjectCard | Project card: name, score, classification, red flags, key metrics |
| ScoreRadar | Radial chart of 7 scoring categories (recharts / Chart.js) |
| ModuleStatus | All module statuses: success/error/running/pending |
| AlertFeed | Live alert feed: new projects 80+, whale activity, red flags |
| Watchlist | Saved projects with score history and trend charts |
| ProjectDetail | Detail page: all modules, tokenomics charts, holder pie chart |

---

## Development Stages

### Stage 1: MVP Core (Week 1–2)
- Core: module_interface, module_registry, result_aggregator, logger
- FastAPI skeleton with health check and basic endpoints
- PostgreSQL model + async connection (SQLAlchemy 2.0)
- 1 module: CoinGecko Discovery (cap < $50M, volume/mcap > 10%)
- Basic frontend: list of found projects + module statuses
- Tests: unit + integration for core and first module

### Stage 2: Analysis Pipeline (Week 3–4)
- Tokenomics analyzer (FDV, FDV/MCap, vesting, supply ratio)
- On-chain analyzer (DefiLlama TVL, Etherscan holders, DAU)
- GitHub analyzer (commits/week, contributors, recency)
- Contract auditor (TokenSniffer, rugcheck, honeypot check)
- Holder distribution analyzer
- Redis cache for API responses with TTL strategy

### Stage 3: Signals (Week 5–6)
- DexScreener integration (new pairs, volume spikes, trending)
- Whale / Smart Money detector
- Red flag detector with penalty scoring
- Narrative analyzer (categories, trends)

### Stage 4: Scoring & Intelligence (Week 7–8)
- Scoring engine with 7 categories + penalty system
- Social momentum tracking (Twitter, Telegram, Discord)
- Exchange listing tracker
- Alert system: Telegram Bot + email notifications
- ScoreRadar component in frontend

### Stage 5: Production (Week 9–10)
- Scheduler: auto-discovery every 6 hours, deep analysis on trigger
- Dashboard polish: filters, radar charts, trend graphs
- Watchlist with push notifications and score history
- Docker-compose: PostgreSQL + Redis + backend + frontend
- Documentation + README

---

## Current Task

**We are starting with Stage 1: MVP Core.**

Work step by step. Do not jump ahead to Stage 2 or beyond until Stage 1 is fully complete and tested.
