import pytest
from app.modules.analysis.github_analyzer import GitHubAnalyzer
from app.core.module_interface import ModuleStatus


@pytest.mark.asyncio
async def test_no_projects_returns_error():
    analyzer = GitHubAnalyzer()
    result = await analyzer.run(projects=None)
    assert result.status == ModuleStatus.ERROR


def test_parse_github_url():
    analyzer = GitHubAnalyzer()

    owner, repo = analyzer._parse_github_url("https://github.com/ethereum/go-ethereum")
    assert owner == "ethereum"
    assert repo == "go-ethereum"

    owner, repo = analyzer._parse_github_url("https://github.com/solana-labs/solana/tree/main")
    assert owner == "solana-labs"
    assert repo == "solana"

    owner, repo = analyzer._parse_github_url("https://invalid-url.com")
    assert owner is None
    assert repo is None
