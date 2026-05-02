from __future__ import annotations

from plugins.analysis.hotspot_discovery import tool_hotspot_discovery
import pandas as pd


def test_tool_hotspot_discovery_outputs_ranked_hotspots(monkeypatch) -> None:
    monkeypatch.setattr(
        "plugins.analysis.hotspot_discovery.tool_sector_heat_score",
        lambda **kwargs: {
            "success": True,
            "sectors": [
                {
                    "name": "半导体",
                    "score": 76,
                    "limit_up_count": 6,
                    "phase": "高潮",
                    "leaders": [{"name": "中芯国际"}, {"name": "北方华创"}],
                },
                {
                    "name": "通信设备",
                    "score": 55,
                    "limit_up_count": 3,
                    "phase": "发酵",
                    "leaders": [{"name": "中际旭创"}],
                },
            ],
        },
    )
    monkeypatch.setattr(
        "plugins.analysis.hotspot_discovery.tool_fetch_sector_data",
        lambda **kwargs: {
            "success": True,
            "all_data": [
                {"sector_name": "半导体", "change_percent": 3.1},
                {"sector_name": "通信设备", "change_percent": 1.4},
            ],
        },
    )
    monkeypatch.setattr(
        "plugins.analysis.hotspot_discovery.tool_fetch_a_share_fund_flow",
        lambda **kwargs: {
            "success": True,
            "data": {
                "records": [
                    {"sector_name": "半导体", "主力净流入": 4.2e9},
                    {"sector_name": "通信设备", "主力净流入": 2.1e9},
                ]
            },
        },
    )

    out = tool_hotspot_discovery(date="2026-04-29", top_k=2, min_heat_score=0)
    hotspots = out["hotspots"]

    assert out["success"] is True
    assert out["quality_status"] == "ok"
    assert len(hotspots) == 2
    assert hotspots[0]["rank"] == 1
    assert hotspots[0]["name"] == "半导体"
    assert "heat_components" in hotspots[0]
    assert hotspots[0]["top_stocks"] == ["中芯国际", "北方华创"]


def test_tool_hotspot_discovery_marks_degraded_when_upstream_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("plugins.analysis.hotspot_discovery.tool_sector_heat_score", lambda **kwargs: {"success": False})
    monkeypatch.setattr("plugins.analysis.hotspot_discovery.tool_fetch_sector_data", lambda **kwargs: {"success": False})
    monkeypatch.setattr("plugins.analysis.hotspot_discovery.tool_fetch_a_share_fund_flow", lambda **kwargs: {"success": False})

    out = tool_hotspot_discovery(date="2026-04-29")

    assert out["success"] is True
    assert out["quality_status"] == "degraded"
    assert isinstance(out.get("degraded_reason"), str)


def test_tool_hotspot_discovery_uses_board_change_fallback(monkeypatch) -> None:
    monkeypatch.setattr("plugins.analysis.hotspot_discovery.tool_sector_heat_score", lambda **kwargs: {"success": False, "sectors": []})
    monkeypatch.setattr("plugins.analysis.hotspot_discovery.tool_fetch_sector_data", lambda **kwargs: {"success": False, "all_data": []})
    monkeypatch.setattr("plugins.analysis.hotspot_discovery.tool_fetch_a_share_fund_flow", lambda **kwargs: {"success": False, "data": {"records": []}})

    class _AkStub:
        @staticmethod
        def stock_board_change_em():
            return pd.DataFrame(
                [
                    {"板块名称": "半导体", "涨跌幅": 2.2, "主力净流入": 12000, "板块异动总次数": 120, "板块异动最频繁个股及所属类型-股票名称": "中芯国际"},
                    {"板块名称": "通信设备", "涨跌幅": 1.5, "主力净流入": 8000, "板块异动总次数": 90, "板块异动最频繁个股及所属类型-股票名称": "中际旭创"},
                ]
            )

    monkeypatch.setattr("plugins.analysis.hotspot_discovery.ak", _AkStub)

    out = tool_hotspot_discovery(date="2026-04-29", top_k=2, min_heat_score=10)
    assert out["success"] is True
    assert len(out["hotspots"]) >= 1
    assert out["hotspots"][0]["phase"] == "盘中异动"
