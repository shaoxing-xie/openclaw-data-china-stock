from plugins.data_collection.index import fetch_global


def test_fetch_global_returns_route_and_observability(monkeypatch):
    monkeypatch.setattr(
        fetch_global,
        "_load_global_latest_config",
        lambda: {"fmp": {}, "priority": ["yfinance", "fmp", "sina"], "root_config": {}, "throttle": {}},
    )
    monkeypatch.setattr(fetch_global, "_resolve_fmp_api_keys", lambda _cfg: [])
    monkeypatch.setattr(
        fetch_global,
        "_fetch_yfinance",
        lambda symbols, _cfg: {
            "success": True,
            "data": [{"code": s, "name": s, "price": 1.0, "change": 0.0, "change_pct": 0.0, "timestamp": "2026-01-01"} for s in symbols],
            "attempt_count": 1,
            "path": "fast_batch",
        },
    )

    result = fetch_global.fetch_global_index_spot("^DJI,^IXIC")

    assert result["success"] is True
    assert result["quality"] == "ok"
    assert result["source_route"]["metric"] == "global.index.default"
    assert result["source_route"]["route"] == ["yfinance", "fmp", "sina"]
    assert result["source_route"].get("catalog_merge", {}).get("merge_mode")
    assert isinstance(result["elapsed_ms"], int)
    assert result["attempts"][0]["source_id"] == "yfinance"


def test_fetch_global_fmp_key_missing_failure_code(monkeypatch):
    monkeypatch.setattr(
        fetch_global,
        "_load_global_latest_config",
        lambda: {"fmp": {}, "priority": ["fmp"], "root_config": {}, "throttle": {}},
    )
    monkeypatch.setattr(fetch_global, "_resolve_fmp_api_keys", lambda _cfg: [])

    result = fetch_global.fetch_global_index_spot("^GSPC")

    assert result["success"] is False
    assert result["failure_code"] == "CONFIG_MISSING_KEY"
    assert result["degraded_reason"] == "CONFIG_MISSING_KEY"
    assert result["attempts"][0]["failure_code"] == "CONFIG_MISSING_KEY"


def test_merge_global_index_spot_reorders_within_config():
    from plugins.utils.plugin_data_registry import merge_global_index_spot_priority

    merged, meta = merge_global_index_spot_priority(["fmp", "yfinance", "sina"])
    assert meta.get("merge_mode") == "catalog_first_then_config_remainder"
    assert merged[0] == "yfinance"
    assert set(merged) == {"yfinance", "fmp", "sina"}


def test_fetch_global_throttle_policy_defaults():
    policy = fetch_global._source_policy({}, "yfinance")
    assert policy["min_interval_sec"] == 0.85
    assert policy["retry_budget"] == 1
