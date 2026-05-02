from __future__ import annotations

import pandas as pd

from plugins.data_collection.limit_up.fetch_limit_up import tool_fetch_limit_up_stocks


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_intraday_uses_strong_pool_when_main_pool_too_small(monkeypatch) -> None:
    em_rows = _df(
        [
            {"代码": "000001", "名称": "A", "涨跌幅": 10.0, "所属行业": "银行", "连板数": 1},
            {"代码": "000002", "名称": "B", "涨跌幅": 9.9, "所属行业": "电子", "连板数": 1},
        ]
    )
    strong_rows = _df(
        [
            {"代码": "000003", "名称": "C", "涨跌幅": 8.2, "所属行业": "电子", "连板数": 2},
            {"代码": "000004", "名称": "D", "涨跌幅": 7.1, "所属行业": "通信", "连板数": 1},
            {"代码": "000005", "名称": "E", "涨跌幅": 6.4, "所属行业": "通信", "连板数": 1},
        ]
    )

    def _fake_fetch(name: str, date: str):
        if name == "stock_zt_pool_em":
            return em_rows, None
        if name == "stock_zt_pool_strong_em":
            return strong_rows, None
        return pd.DataFrame(), None

    monkeypatch.setattr("plugins.data_collection.limit_up.fetch_limit_up._fetch_pool_df", _fake_fetch)
    monkeypatch.setattr("plugins.data_collection.limit_up.fetch_limit_up.cache_get", lambda key: None)
    monkeypatch.setattr("plugins.data_collection.limit_up.fetch_limit_up.cache_set", lambda key, value, ttl: None)
    monkeypatch.setattr("plugins.data_collection.limit_up.fetch_limit_up._is_same_day_intraday", lambda d: True)

    out = tool_fetch_limit_up_stocks(date="20260429")

    assert out["success"] is True
    assert out["count"] >= 3
    assert "strong_em+em" in str(out.get("source"))
