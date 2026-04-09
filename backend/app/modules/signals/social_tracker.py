import httpx
from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)

COINGECKO_API = "https://api.coingecko.com/api/v3"


class SocialTracker(BaseModule):
    """Stage 4 — Social Momentum Tracker.

    Measures social activity dynamics: Twitter followers, Telegram/Reddit
    community size, and engagement metrics.
    Uses CoinGecko community_data + developer_data as the free-tier source.
    """

    name = "social_tracker"

    async def run(
        self,
        projects: list[dict] | None = None,
        coin_details: dict | None = None,
    ) -> ModuleResult:
        if not projects:
            return self.fail("No projects to analyse")

        results = []
        warnings = []

        for p in projects:
            cg_id = p.get("id")
            if not cg_id:
                continue

            detail = (coin_details or {}).get(cg_id)
            if not detail:
                warnings.append(f"No data for {cg_id}")
                continue

            analysis = self._analyse_social(cg_id, detail)
            results.append(analysis)

        logger.info(f"SocialTracker: analysed {len(results)}/{len(projects)} projects")
        return self.ok(
            data={"analyses": results},
            message=f"Analysed {len(results)} projects",
            warnings=warnings or None,
        )

    def _analyse_social(self, cg_id: str, detail: dict) -> dict:
        community = detail.get("community_data") or {}
        sentiment = detail.get("sentiment_votes_up_percentage") or 0

        # Twitter
        twitter_followers = community.get("twitter_followers") or 0

        # Telegram
        telegram_members = community.get("telegram_channel_user_count") or 0

        # Reddit
        reddit_subs = community.get("reddit_subscribers") or 0
        reddit_active = community.get("reddit_accounts_active_48h") or 0

        # Engagement signals
        signals = []
        score = 0

        # Twitter scoring (max 3 pts)
        if twitter_followers > 100_000:
            signals.append(f"Large Twitter: {twitter_followers:,} followers")
            score += 3
        elif twitter_followers > 20_000:
            signals.append(f"Good Twitter: {twitter_followers:,} followers")
            score += 2
        elif twitter_followers > 5_000:
            score += 1

        # Telegram scoring (max 2 pts)
        if telegram_members > 50_000:
            signals.append(f"Large Telegram: {telegram_members:,} members")
            score += 2
        elif telegram_members > 10_000:
            signals.append(f"Active Telegram: {telegram_members:,} members")
            score += 1

        # Reddit scoring (max 2 pts)
        if reddit_subs > 50_000:
            signals.append(f"Large Reddit: {reddit_subs:,} subs")
            score += 2
        elif reddit_subs > 10_000:
            score += 1

        # Engagement ratio: active reddit users / subscribers
        if reddit_subs > 0:
            engagement_ratio = reddit_active / reddit_subs
            if engagement_ratio > 0.05:
                signals.append(f"High Reddit engagement: {engagement_ratio:.1%}")
                score += 1

        # Sentiment bonus (max 2 pts)
        if sentiment > 80:
            signals.append(f"Strong sentiment: {sentiment:.0f}% positive")
            score += 2
        elif sentiment > 60:
            score += 1

        # Red flags
        red_flags = []
        if twitter_followers == 0 and telegram_members == 0:
            red_flags.append("No social presence (0 Twitter + 0 Telegram)")

        return {
            "project_id": cg_id,
            "twitter_followers": twitter_followers,
            "telegram_members": telegram_members,
            "reddit_subscribers": reddit_subs,
            "reddit_active_48h": reddit_active,
            "sentiment_up_pct": sentiment,
            "social_signals": signals,
            "social_score": min(score, 10),  # max 10 pts per ТЗ
            "red_flags": red_flags,
        }
