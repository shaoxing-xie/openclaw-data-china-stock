"""cache.py TTL 上限淘汰、装饰器命中拷贝、汇总统计。"""

from __future__ import annotations

import time

from plugins.utils import cache as cache_mod


def test_ttl_cache_max_entries_eviction():
    c = cache_mod.TTLCache(default_ttl=3600, max_entries=3)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)
    assert len(c.cache) == 3
    c.set("d", 4)
    assert len(c.cache) == 3
    assert c.get("a") is None
    assert c.get("d") == 4
    assert c.eviction_count >= 1


def test_cache_result_success_only_and_hit_copy():
    calls = {"n": 0}

    @cache_mod.cache_result(
        cache_type="result",
        ttl=300,
        max_entries=50,
        cache_success_only=True,
        copy_on_hit=True,
        key_prefix="t_test",
    )
    def _fn(x: int) -> dict:
        calls["n"] += 1
        return {"success": x > 0, "v": x}

    r1 = _fn(1)
    assert r1["success"] is True
    assert "_cache_hit" not in r1
    r2 = _fn(1)
    assert calls["n"] == 1
    assert r2.get("_cache_hit") is True
    r2["mutate"] = True
    r3 = _fn(1)
    assert "mutate" not in r3

    _fn(0)
    _fn(0)
    assert calls["n"] == 3


def test_get_detailed_stats_has_fund_flow_bucket():
    st = cache_mod.get_detailed_stats()
    assert "fund_flow_tool_memory" in st
    assert "total_evictions" in st
