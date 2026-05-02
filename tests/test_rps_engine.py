from plugins.analysis.rps_engine import _rps_from_returns, calculate_rps_for_etfs


def test_rps_from_returns_monotonic():
    points = _rps_from_returns([("A", 0.3), ("B", 0.1), ("C", -0.1)])
    assert [p.code for p in points] == ["A", "B", "C"]
    assert points[0].rps > points[1].rps > points[2].rps
    assert points[0].rank == 1


def test_calculate_rps_for_etfs_happy(monkeypatch):
    # Patch market data tool to return synthetic klines.
    def _fake_tool_fetch_market_data(**kwargs):
        code = kwargs.get("asset_code")
        base = {"A": 100.0, "B": 100.0, "C": 100.0}.get(code, 100.0)
        last = {"A": 110.0, "B": 105.0, "C": 95.0}.get(code, 100.0)
        klines = [{"date": "2026-04-01", "close": base}, {"date": "2026-04-30", "close": last}]
        return {"success": True, "data": {"klines": klines}, "source": "test"}

    import plugins.merged.fetch_market_data as fm

    monkeypatch.setattr(fm, "tool_fetch_market_data", _fake_tool_fetch_market_data)

    out = calculate_rps_for_etfs(etf_codes=["A", "B", "C"], lookback_days=20, trade_date="2026-04-30")
    assert out["success"] is True
    rps = out["data"]["rps"]
    assert rps["A"]["rank"] == 1
    assert rps["C"]["rank"] == 3

