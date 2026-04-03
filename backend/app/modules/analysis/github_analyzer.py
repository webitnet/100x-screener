import asyncio
import re
import httpx
from datetime import datetime, timezone
from app.core.module_interface import BaseModule, ModuleResult
from app.core.logger import get_logger

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubAnalyzer(BaseModule):
    name = "github_analyzer"

    async def run(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        if not projects:
            return self.fail("No projects to analyse")

        results = []
        warnings = []
        async with httpx.AsyncClient(timeout=20) as client:
            for p in projects:
                cg_id = p.get("id")
                if not cg_id:
                    continue
                detail = (coin_details or {}).get(cg_id)
                if not detail:
                    warnings.append(f"No data for {cg_id}")
                    continue

                repos = detail.get("links", {}).get("repos_url", {}).get("github", [])
                if not repos:
                    warnings.append(f"No GitHub repo for {cg_id}")
                    continue

                owner, repo = self._parse_github_url(repos[0])
                if not owner or not repo:
                    continue

                analysis = await self._fetch_github_stats(client, cg_id, owner, repo)
                if analysis:
                    results.append(analysis)
                else:
                    warnings.append(f"Could not fetch GitHub stats for {cg_id}")
                await asyncio.sleep(0.5)

        logger.info(f"GitHub: analysed {len(results)}/{len(projects)} projects")
        return self.ok(
            data={"analyses": results},
            message=f"Analysed {len(results)} projects",
            warnings=warnings or None,
        )

    def _parse_github_url(self, url: str) -> tuple[str | None, str | None]:
        parts = url.rstrip("/").split("/")
        try:
            idx = parts.index("github.com")
            owner = parts[idx + 1] if len(parts) > idx + 1 else None
            repo = parts[idx + 2] if len(parts) > idx + 2 else None
            return owner, repo
        except (ValueError, IndexError):
            return None, None

    async def _fetch_github_stats(
        self, client: httpx.AsyncClient, coingecko_id: str, owner: str, repo: str
    ) -> dict | None:
        try:
            resp = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
            if resp.status_code != 200:
                return None
            repo_data = resp.json()

            await asyncio.sleep(0.3)

            since = datetime.now(timezone.utc).replace(day=1).isoformat()
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/commits",
                params={"since": since, "per_page": 100},
            )
            commits = resp.json() if resp.status_code == 200 and isinstance(resp.json(), list) else []

            await asyncio.sleep(0.3)

            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contributors",
                params={"per_page": 1, "anon": "true"},
            )
            contributors = 0
            if resp.status_code == 200:
                link = resp.headers.get("link", "")
                if 'rel="last"' in link:
                    match = re.search(r'page=(\d+)>; rel="last"', link)
                    contributors = int(match.group(1)) if match else len(resp.json())
                else:
                    contributors = len(resp.json())

            last_push = repo_data.get("pushed_at", "")
            days_since_push = None
            if last_push:
                try:
                    dt = datetime.fromisoformat(last_push.replace("Z", "+00:00"))
                    days_since_push = (datetime.now(timezone.utc) - dt).days
                except Exception:
                    pass

            red_flags = []
            if days_since_push is not None and days_since_push > 30:
                red_flags.append(f"GitHub silent {days_since_push} days")

            score = 0
            commits_count = len(commits)
            if commits_count >= 20:
                score += 8
            elif commits_count >= 10:
                score += 5
            elif commits_count >= 3:
                score += 2

            if contributors >= 10:
                score += 5
            elif contributors >= 5:
                score += 3
            elif contributors >= 2:
                score += 1

            stars = repo_data.get("stargazers_count", 0)
            if stars >= 500:
                score += 4
            elif stars >= 100:
                score += 2
            elif stars >= 20:
                score += 1

            if days_since_push is not None and days_since_push <= 7:
                score += 3
            elif days_since_push is not None and days_since_push <= 30:
                score += 1

            return {
                "project_id": coingecko_id,
                "github_url": f"https://github.com/{owner}/{repo}",
                "stars": stars,
                "forks": repo_data.get("forks_count", 0),
                "commits_last_month": commits_count,
                "contributors": contributors,
                "days_since_last_push": days_since_push,
                "github_score": min(score, 20),
                "red_flags": red_flags,
            }
        except Exception as exc:
            logger.warning(f"GitHub stats error for {owner}/{repo}: {exc}")
            return None
