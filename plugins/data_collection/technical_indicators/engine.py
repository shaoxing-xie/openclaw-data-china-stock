from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Tuple


@dataclass
class EngineSelection:
    name: str
    talib: object | None
    pandas_ta: object | None


class TechnicalIndicatorEngine:
    @staticmethod
    def _load_backend_modules() -> Tuple[Any, Any]:
        talib_mod = None
        pta_mod = None
        try:
            import talib as _talib  # type: ignore

            talib_mod = _talib
        except Exception:
            talib_mod = None

        try:
            import pandas_ta as _pta  # type: ignore

            pta_mod = _pta
        except Exception:
            pta_mod = None

        return talib_mod, pta_mod

    @staticmethod
    def catalog_auto_engine_order() -> List[str]:
        """
        Order for ``engine_preference=auto`` from ``source_chains.technical_indicators``.

        Falls back to talib → pandas_ta → builtin when catalog empty or no recognized tags.
        """
        try:
            from plugins.utils.plugin_data_registry import get_source_chain

            raw = get_source_chain("technical_indicators").get("provider_tags") or []
        except Exception:
            raw = []

        out: List[str] = []
        for x in raw:
            s = str(x).lower().strip().replace("-", "_")
            if s in ("pandas_ta", "pandasta"):
                tag = "pandas_ta"
            elif s in ("talib", "builtin"):
                tag = s
            else:
                continue
            if tag not in out:
                out.append(tag)
        return out if out else ["talib", "pandas_ta", "builtin"]

    @staticmethod
    def select(engine_preference: str = "auto") -> EngineSelection:
        pref = (engine_preference or "auto").strip().lower()
        talib_mod, pta_mod = TechnicalIndicatorEngine._load_backend_modules()

        if pref == "talib":
            if talib_mod is None:
                raise RuntimeError("TA-Lib 不可用，无法满足 engine_preference=talib")
            return EngineSelection(name="talib", talib=talib_mod, pandas_ta=pta_mod)

        if pref == "pandas_ta":
            if pta_mod is None:
                raise RuntimeError("pandas-ta 不可用，无法满足 engine_preference=pandas_ta")
            return EngineSelection(name="pandas_ta", talib=talib_mod, pandas_ta=pta_mod)

        # auto（含历史遗留未知取值）：按 catalog 顺序选用可用引擎
        for eng in TechnicalIndicatorEngine.catalog_auto_engine_order():
            if eng == "talib" and talib_mod is not None:
                return EngineSelection(name="talib", talib=talib_mod, pandas_ta=pta_mod)
            if eng == "pandas_ta" and pta_mod is not None:
                return EngineSelection(name="pandas_ta", talib=talib_mod, pandas_ta=pta_mod)
            if eng == "builtin":
                return EngineSelection(name="builtin", talib=None, pandas_ta=None)
        return EngineSelection(name="builtin", talib=None, pandas_ta=None)
