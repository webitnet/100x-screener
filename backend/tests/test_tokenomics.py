import pytest
from unittest.mock import AsyncMock, patch
from app.modules.analysis.tokenomics_analyzer import TokenomicsAnalyzer
from app.core.module_interface import ModuleStatus


MOCK_COIN_RESPONSE = {
    "name": "TestToken",
    "market_data": {
        "market_cap": {"usd": 10_000_000},
        "fully_diluted_valuation": {"usd": 30_000_000},
        "circulating_supply": 50_000_000,
        "total_supply": 100_000_000,
        "max_supply": 200_000_000,
    },
}

MOCK_COIN_HIGH_FDV = {
    "name": "DilutedToken",
    "market_data": {
        "market_cap": {"usd": 5_000_000},
        "fully_diluted_valuation": {"usd": 100_000_000},
        "circulating_supply": 1_000_000,
        "total_supply": 100_000_000,
        "max_supply": 100_000_000,
    },
}


@pytest.mark.asyncio
async def test_no_projects_returns_error():
    analyzer = TokenomicsAnalyzer()
    result = await analyzer.run(projects=None)
    assert result.status == ModuleStatus.ERROR


@pytest.mark.asyncio
async def test_extract_tokenomics_healthy():
    analyzer = TokenomicsAnalyzer()
    t = analyzer._extract_tokenomics("test-token", MOCK_COIN_RESPONSE)

    assert t["fdv_to_mcap"] == 3.0
    assert t["circulating_to_total"] == 0.5
    assert t["circulating_to_max"] == 0.25
    assert t["tokenomics_score"] >= 15  # healthy token, minor deductions
    assert len(t["red_flags"]) == 0


@pytest.mark.asyncio
async def test_extract_tokenomics_high_fdv_flags():
    analyzer = TokenomicsAnalyzer()
    t = analyzer._extract_tokenomics("diluted-token", MOCK_COIN_HIGH_FDV)

    assert t["fdv_to_mcap"] == 20.0
    assert t["tokenomics_score"] <= 5  # heavy penalties
    assert any("FDV/MCap" in f for f in t["red_flags"])
    assert any("circulating" in f for f in t["red_flags"])
