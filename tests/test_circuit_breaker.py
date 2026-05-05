"""circuit_breaker：OPEN 快速失败与全局开关。"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_breakers(monkeypatch):
    from plugins.utils import circuit_breaker as cb

    monkeypatch.delenv("OPENCLAW_CIRCUIT_BREAKER_ENABLED", raising=False)
    cb.reset_all_breakers_for_tests()
    yield
    cb.reset_all_breakers_for_tests()


def test_circuit_disabled_passes_through(monkeypatch):
    from plugins.utils.circuit_breaker import call_or_pass_through

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return {"success": True}

    assert call_or_pass_through("k1", fn)["success"] is True
    assert calls["n"] == 1


def test_circuit_open_skips_fn(monkeypatch):
    monkeypatch.setenv("OPENCLAW_CIRCUIT_BREAKER_ENABLED", "1")
    monkeypatch.setenv("OPENCLAW_CB_FAILURE_THRESHOLD", "1")
    from plugins.utils.circuit_breaker import call_or_pass_through

    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise RuntimeError("upstream")

    try:
        call_or_pass_through("trip", boom)
    except RuntimeError:
        pass
    out = call_or_pass_through("trip", boom)
    assert out.get("error_code") == "CIRCUIT_OPEN"
    assert calls["n"] == 1


def test_would_block_next_call_when_open(monkeypatch):
    monkeypatch.setenv("OPENCLAW_CIRCUIT_BREAKER_ENABLED", "1")
    monkeypatch.setenv("OPENCLAW_CB_FAILURE_THRESHOLD", "1")
    from plugins.utils import circuit_breaker as cb

    br = cb.get_breaker("wb")
    assert br.would_block_next_call() is False
    br.record_failure()
    assert br.would_block_next_call() is True
