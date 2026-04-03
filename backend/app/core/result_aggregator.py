from app.core.module_interface import ModuleResult, ModuleStatus
from app.core.logger import get_logger

logger = get_logger(__name__)


class ResultAggregator:
    def aggregate(self, results: dict[str, ModuleResult]) -> dict:
        successful = {}
        failed = {}
        warnings = {}

        for name, result in results.items():
            if result.status == ModuleStatus.SUCCESS:
                successful[name] = result
            elif result.status == ModuleStatus.WARNING:
                warnings[name] = result
                successful[name] = result  # warnings still carry usable data
            else:
                failed[name] = result
                logger.warning(f"Module {name} failed: {result.message}")

        projects = self._merge_project_data({**successful, **warnings})

        return {
            "total_modules": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "warnings": len(warnings),
            "failed_modules": [
                {"name": n, "message": r.message} for n, r in failed.items()
            ],
            "projects": projects,
        }

    def _merge_project_data(self, results: dict[str, ModuleResult]) -> list[dict]:
        """Merge project lists from all successful modules into a unified list."""
        seen: dict[str, dict] = {}

        for result in results.values():
            for project in result.data.get("projects", []):
                key = project.get("id") or project.get("ticker") or project.get("name", "")
                if key not in seen:
                    seen[key] = project
                else:
                    seen[key].update(project)

        return list(seen.values())


aggregator = ResultAggregator()
