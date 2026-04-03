from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel


class ModuleStatus:
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    TIMEOUT = "timeout"
    RUNNING = "running"
    PENDING = "pending"


class ModuleResult(BaseModel):
    module_name: str
    status: str
    message: str
    data: dict[str, Any] = {}
    warnings: list[str] = []
    updated_at: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()


class BaseModule(ABC):
    name: str = "base_module"

    @abstractmethod
    async def run(self, projects: list[dict] | None = None, coin_details: dict | None = None) -> ModuleResult:
        """Execute the module and return a standardised result.

        Discovery modules ignore `projects` and `coin_details`.
        Analysis modules receive discovered projects and pre-fetched CoinGecko data.
        """

    def ok(self, data: dict, message: str = "OK", warnings: list[str] | None = None) -> ModuleResult:
        return ModuleResult(
            module_name=self.name,
            status=ModuleStatus.SUCCESS,
            message=message,
            data=data,
            warnings=warnings or [],
        )

    def fail(self, message: str, data: dict | None = None) -> ModuleResult:
        return ModuleResult(
            module_name=self.name,
            status=ModuleStatus.ERROR,
            message=message,
            data=data or {},
        )

    def warn(self, message: str, data: dict, warnings: list[str]) -> ModuleResult:
        return ModuleResult(
            module_name=self.name,
            status=ModuleStatus.WARNING,
            message=message,
            data=data,
            warnings=warnings,
        )
