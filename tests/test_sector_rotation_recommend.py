import plugins.analysis.sector_rotator as rot
from plugins.analysis.sector_rotator import tool_sector_rotation_recommend


def _patch_market_data(monkeypatch, *, shrink_last: bool = False):
    def _fake_fetch_market_data(**kwargs):
        lb = int(kwargs.get("lookback_days") or 5)
        n = max(lb, 3)
        klines = []
        for i in range(n):
            vol = 2_000_000.0
            if shrink_last and i == n - 1:
                vol = 300_000.0
            elif (not shrink_last) and i == n - 1:
                vol = 5_000_000.0
            klines.append({"date": f"2026-03-{(i % 28) + 1:02d}", "amount": 200000000, "close": 1.0, "volume": vol})
        return {"success": True, "data": {"klines": klines}}

    import plugins.merged.fetch_market_data as fm

    monkeypatch.setattr(fm, "tool_fetch_market_data", _fake_fetch_market_data)


def test_sector_rotation_recommend_smoke(monkeypatch):
    # Patch RPS calculation to be deterministic and avoid network.
    def _fake_rps(*, etf_codes, lookback_days, trade_date="", mode="production"):
        # Higher code -> higher return/rps
        rps_map = {}
        for i, code in enumerate(etf_codes):
            rps_map[code] = {"rps": float(100 - i), "rank": i + 1, "return": float(0.01 * (len(etf_codes) - i))}
        return {"success": True, "quality_status": "ok", "data": {"rps": rps_map}}

    monkeypatch.setattr(rot, "calculate_rps_for_etfs", _fake_rps)
    _patch_market_data(monkeypatch)

    out = tool_sector_rotation_recommend(top_k=3, trade_date="2026-04-30", min_liquidity=100000000)
    assert out["success"] is True
    recs = out["data"]["recommendations"]
    assert len(recs) == 3
    assert recs[0]["rank"] == 1
    assert "signals" in recs[0]
    env = out["data"]["environment"]
    assert env["gate"] == "GO"
    assert env["allocation_multiplier"] == 1.0
    assert "env_gate_go" in env["reason_codes"]
    assert all(r["allocation_pct"] == min(20, int(round(100 / 5))) for r in recs)
    assert recs[0]["signals"].get("volume_status") == "surge"
    assert isinstance(recs[0].get("explain_bullets"), list) and recs[0]["explain_bullets"]
    assert out["data"]["fundamentals_lane"]["reason_code"] == "fundamental_data_unavailable"


def test_env_gate_caution_allocation_scaled(monkeypatch):
    def _fake_rps(*, etf_codes, lookback_days, trade_date="", mode="production"):
        rps_map = {}
        for i, code in enumerate(etf_codes):
            # ~20% strong (>=85): first 4 codes at 90, rest weak
            rps_val = 90.0 if i < 4 else 40.0
            rps_map[code] = {"rps": rps_val, "rank": i + 1, "return": 0.01 if i < 4 else -0.02}
        return {"success": True, "quality_status": "ok", "data": {"rps": rps_map}}

    monkeypatch.setattr(rot, "calculate_rps_for_etfs", _fake_rps)
    _patch_market_data(monkeypatch)

    out = tool_sector_rotation_recommend(top_k=5, trade_date="2026-04-30", min_liquidity=100000000)
    assert out["data"]["environment"]["gate"] == "CAUTION"
    base = min(20, int(round(100 / max(5, 5))))
    assert all(r["allocation_pct"] == int(round(base * 0.5)) for r in out["data"]["recommendations"])


def test_env_gate_stop_keeps_rows_zero_allocation(monkeypatch):
    def _fake_rps(*, etf_codes, lookback_days, trade_date="", mode="production"):
        rps_map = {code: {"rps": 30.0, "rank": i + 1, "return": -0.02} for i, code in enumerate(etf_codes)}
        return {"success": True, "quality_status": "ok", "data": {"rps": rps_map}}

    monkeypatch.setattr(rot, "calculate_rps_for_etfs", _fake_rps)
    _patch_market_data(monkeypatch)

    out = tool_sector_rotation_recommend(top_k=3, trade_date="2026-04-30", min_liquidity=100000000)
    assert out["data"]["environment"]["gate"] == "STOP"
    recs = out["data"]["recommendations"]
    assert len(recs) == 3
    assert all(r["allocation_pct"] == 0 for r in recs)
    assert all("rotation_paused_env_stop" in (r.get("cautions") or []) for r in recs)


def test_env_gate_disabled_unknown(monkeypatch):
    def _fake_rps(*, etf_codes, lookback_days, trade_date="", mode="production"):
        rps_map = {}
        for i, code in enumerate(etf_codes):
            rps_map[code] = {"rps": float(100 - i), "rank": i + 1, "return": 0.01}
        return {"success": True, "quality_status": "ok", "data": {"rps": rps_map}}

    monkeypatch.setattr(rot, "calculate_rps_for_etfs", _fake_rps)
    monkeypatch.setattr(rot, "_load_env_gate_config", lambda: {**rot._default_env_gate_config(), "enabled": False})
    _patch_market_data(monkeypatch)

    out = tool_sector_rotation_recommend(top_k=3, trade_date="2026-04-30", min_liquidity=100000000)
    env = out["data"]["environment"]
    assert env["gate"] == "UNKNOWN"
    assert "env_gate_disabled" in env["reason_codes"]
    assert out["data"]["recommendations"][0]["allocation_pct"] > 0


def test_volume_shrink_adds_caution(monkeypatch):
    def _fake_rps(*, etf_codes, lookback_days, trade_date="", mode="production"):
        rps_map = {}
        for i, code in enumerate(etf_codes):
            rps_map[code] = {"rps": float(100 - i), "rank": i + 1, "return": 0.01}
        return {"success": True, "quality_status": "ok", "data": {"rps": rps_map}}

    monkeypatch.setattr(rot, "calculate_rps_for_etfs", _fake_rps)
    _patch_market_data(monkeypatch, shrink_last=True)

    out = tool_sector_rotation_recommend(top_k=1, trade_date="2026-04-30", min_liquidity=100000000)
    r0 = out["data"]["recommendations"][0]
    assert r0["signals"].get("volume_status") == "shrink"
    assert "volume_shrink_fake_breakout_risk" in (r0.get("cautions") or [])

