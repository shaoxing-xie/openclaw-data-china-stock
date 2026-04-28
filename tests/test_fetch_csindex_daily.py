from plugins.data_collection.index import fetch_csindex_daily


def test_fetch_csindex_daily_success(monkeypatch):
    class _Ak:
        @staticmethod
        def stock_zh_index_hist_csindex(symbol, start_date, end_date):
            import pandas as pd

            return pd.DataFrame(
                [
                    {
                        "日期": "2026-01-02",
                        "开盘": 100.0,
                        "最高": 101.0,
                        "最低": 99.0,
                        "收盘": 100.5,
                        "涨跌幅": 1.2,
                        "成交量": 200000.0,
                        "成交额": 30000000.0,
                    }
                ]
            )

    monkeypatch.setattr(fetch_csindex_daily, "AKSHARE_AVAILABLE", True)
    monkeypatch.setattr(fetch_csindex_daily, "ak", _Ak)

    result = fetch_csindex_daily.fetch_csindex_index_daily("000300", "20260101", "20260110")

    assert result["success"] is True
    assert result["source_id"] == "akshare"
    assert result["quality_status"] == "ok"
    assert result["count"] == 1
    assert result["data"][0]["close"] == 100.5


def test_fetch_csindex_daily_schema_drift(monkeypatch):
    class _Ak:
        @staticmethod
        def stock_zh_index_hist_csindex(symbol, start_date, end_date):
            import pandas as pd

            return pd.DataFrame([{"日期": "2026-01-02", "开盘": 100.0}])

    monkeypatch.setattr(fetch_csindex_daily, "AKSHARE_AVAILABLE", True)
    monkeypatch.setattr(fetch_csindex_daily, "ak", _Ak)

    result = fetch_csindex_daily.fetch_csindex_index_daily("000300", "20260101", "20260110")

    assert result["success"] is False
    assert result["failure_code"] == "UPSTREAM_SCHEMA_DRIFT"
    assert result["quality_status"] == "error"


def test_fetch_csindex_daily_invalid_param():
    result = fetch_csindex_daily.fetch_csindex_index_daily("000300", "2026/01/01", "20260110")
    assert result["success"] is False
    assert result["failure_code"] == "INVALID_PARAM"
