import asyncio
from typing import Type
from app.core.module_interface import BaseModule, ModuleResult, ModuleStatus
from app.core.logger import get_logger

logger = get_logger(__name__)


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, BaseModule] = {}

    def register(self, module: BaseModule) -> None:
        self._modules[module.name] = module
        logger.info(f"Module registered: {module.name}")

    def unregister(self, name: str) -> None:
        self._modules.pop(name, None)
        logger.info(f"Module unregistered: {name}")

    def get(self, name: str) -> BaseModule | None:
        return self._modules.get(name)

    def list_names(self) -> list[str]:
        return list(self._modules.keys())

    async def run_one(self, name: str, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        module = self._modules.get(name)
        if not module:
            return ModuleResult(
                module_name=name,
                status=ModuleStatus.ERROR,
                message=f"Module '{name}' not found in registry",
            )
        try:
            logger.info(f"Running module: {name}")
            result = await module.run(projects=projects, coin_details=coin_details)
            logger.info(f"Module {name} finished with status: {result.status}")
            return result
        except Exception as exc:
            logger.error(f"Module {name} crashed: {exc}", exc_info=True)
            return ModuleResult(
                module_name=name,
                status=ModuleStatus.ERROR,
                message=str(exc),
            )

    async def run_all(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> dict[str, ModuleResult]:
        tasks = {name: self.run_one(name, projects=projects, coin_details=coin_details) for name in self._modules}
        results = await asyncio.gather(*tasks.values(), return_exceptions=False)
        return dict(zip(tasks.keys(), results))


registry = ModuleRegistry()
