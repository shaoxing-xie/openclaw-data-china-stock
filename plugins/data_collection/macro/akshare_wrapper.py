"""AKShare macro wrapper with retry/timeout controls."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Dict

try:
    import akshare as ak
except Exception:  # pragma: no cover - optional in unit-test runtime
    ak = None


@dataclass
class WrapperConfig:
    retries: int = 3
    timeout_seconds: int = 30


class AKShareMacroWrapper:
    """Unified AKShare wrapper for macro data collection."""

    def __init__(self, config: WrapperConfig | None = None):
        self.config = config or WrapperConfig()

    def _run_with_timeout(self, func_name: str, kwargs: Dict[str, Any]) -> Any:
        if ak is None:
            raise RuntimeError("akshare is not installed")
        func = getattr(ak, func_name)
        with ThreadPoolExecutor(max_workers=1) as executor:
            fut = executor.submit(func, **kwargs)
            return fut.result(timeout=self.config.timeout_seconds)

    def fetch(self, func_name: str, **kwargs: Any) -> Dict[str, Any]:
        """Call AKShare function with retries and timeout.

        Returns:
            {
                "success": bool,
                "data": Any | None,
                "attempt": int,
                "error": str | None,
                "error_code": str | None,
            }
        """
        for attempt in range(1, self.config.retries + 1):
            try:
                data = self._run_with_timeout(func_name, kwargs)
                return {
                    "success": True,
                    "data": data,
                    "attempt": attempt,
                    "error": None,
                    "error_code": None,
                }
            except FutureTimeoutError:
                if attempt == self.config.retries:
                    return {
                        "success": False,
                        "data": None,
                        "attempt": attempt,
                        "error": f"AKShare call timeout: {func_name}",
                        "error_code": "UPSTREAM_TIMEOUT",
                    }
            except Exception as exc:  # pragma: no cover - runtime defensive
                if attempt == self.config.retries:
                    return {
                        "success": False,
                        "data": None,
                        "attempt": attempt,
                        "error": str(exc),
                        "error_code": "UPSTREAM_FETCH_FAILED",
                    }
        return {
            "success": False,
            "data": None,
            "attempt": self.config.retries,
            "error": "max retries exceeded",
            "error_code": "UPSTREAM_FETCH_FAILED",
        }

