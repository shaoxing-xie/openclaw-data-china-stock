"""Catalog-driven TA engine order (factor_registry technical_indicators chain)."""

from __future__ import annotations

import pytest

from plugins.data_collection.technical_indicators.engine import TechnicalIndicatorEngine


def test_catalog_auto_engine_order_defaults_when_chain_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "plugins.utils.plugin_data_registry.get_source_chain",
        lambda _k: {},
    )
    assert TechnicalIndicatorEngine.catalog_auto_engine_order() == ["talib", "pandas_ta", "builtin"]


def test_select_auto_prefers_catalog_builtin_when_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "plugins.utils.plugin_data_registry.get_source_chain",
        lambda k: {"provider_tags": ["builtin", "talib"]}
        if k == "technical_indicators"
        else {},
    )
    monkeypatch.setattr(
        "plugins.data_collection.technical_indicators.engine.TechnicalIndicatorEngine._load_backend_modules",
        lambda: (_DummyTalib(), _DummyPta()),
    )
    sel = TechnicalIndicatorEngine.select("auto")
    assert sel.name == "builtin"
    assert sel.talib is None and sel.pandas_ta is None


def test_select_auto_prefers_catalog_pandas_before_talib(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "plugins.utils.plugin_data_registry.get_source_chain",
        lambda k: {"provider_tags": ["pandas_ta", "talib"]}
        if k == "technical_indicators"
        else {},
    )
    monkeypatch.setattr(
        "plugins.data_collection.technical_indicators.engine.TechnicalIndicatorEngine._load_backend_modules",
        lambda: (_DummyTalib(), _DummyPta()),
    )
    sel = TechnicalIndicatorEngine.select("auto")
    assert sel.name == "pandas_ta"


class _DummyTalib:
    pass


class _DummyPta:
    pass
