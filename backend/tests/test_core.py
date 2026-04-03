import pytest
from app.core.module_interface import BaseModule, ModuleResult, ModuleStatus
from app.core.module_registry import ModuleRegistry
from app.core.result_aggregator import ResultAggregator


class OkModule(BaseModule):
    name = "ok_module"

    async def run(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        return self.ok(data={"projects": [{"id": "token-a", "name": "Token A"}]}, message="done")


class FailModule(BaseModule):
    name = "fail_module"

    async def run(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        raise RuntimeError("Something broke")


@pytest.mark.asyncio
async def test_ok_module_returns_success():
    result = await OkModule().run()
    assert result.status == ModuleStatus.SUCCESS
    assert result.module_name == "ok_module"
    assert len(result.data["projects"]) == 1


@pytest.mark.asyncio
async def test_registry_isolates_module_failure():
    reg = ModuleRegistry()
    reg.register(OkModule())
    reg.register(FailModule())

    results = await reg.run_all()

    assert results["ok_module"].status == ModuleStatus.SUCCESS
    assert results["fail_module"].status == ModuleStatus.ERROR


@pytest.mark.asyncio
async def test_aggregator_counts_correctly():
    reg = ModuleRegistry()
    reg.register(OkModule())
    reg.register(FailModule())

    results = await reg.run_all()
    summary = ResultAggregator().aggregate(results)

    assert summary["total_modules"] == 2
    assert summary["successful"] == 1
    assert summary["failed"] == 1
    assert len(summary["projects"]) == 1


@pytest.mark.asyncio
async def test_registry_run_one_missing_module():
    reg = ModuleRegistry()
    result = await reg.run_one("nonexistent")
    assert result.status == ModuleStatus.ERROR
