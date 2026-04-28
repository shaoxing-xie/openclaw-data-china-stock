from plugins.data_collection.index import fetch_cni_daily


def test_fetch_cni_daily_success(monkeypatch):
    class _Ak:
        @staticmethod
        def index_hist_cni(symbol, start_date, end_date):
            import pandas as pd

            return pd.DataFrame(
                [
                    {
                        "日期": "2026-01-02",
                        "开盘价": 100.0,
                        "最高价": 101.0,
                        "最低价": 99.0,
                        "收盘价": 100.5,
                        "涨跌幅": 1.2,
                        "成交量": 2.0,  # 万手
                        "成交额": 3.0,  # 亿元
                    }
                ]
            )

    monkeypatch.setattr(fetch_cni_daily, "AKSHARE_AVAILABLE", True)
    monkeypatch.setattr(fetch_cni_daily, "ak", _Ak)

    result = fetch_cni_daily.fetch_cni_index_daily("399001", "20260101", "20260110")

    assert result["success"] is True
    assert result["source_id"] == "akshare"
    assert result["quality_status"] == "ok"
    assert result["count"] == 1
    assert result["data"][0]["volume_raw"] == 2.0
    assert result["data"][0]["volume"] == 20000.0
    assert result["data"][0]["amount_raw"] == 3.0
    assert result["data"][0]["amount"] == 300000000.0


def test_fetch_cni_daily_schema_drift(monkeypatch):
    class _Ak:
        @staticmethod
        def index_hist_cni(symbol, start_date, end_date):
            import pandas as pd

            return pd.DataFrame([{"日期": "2026-01-02", "开盘价": 100.0}])

    monkeypatch.setattr(fetch_cni_daily, "AKSHARE_AVAILABLE", True)
    monkeypatch.setattr(fetch_cni_daily, "ak", _Ak)

    result = fetch_cni_daily.fetch_cni_index_daily("399001", "20260101", "20260110")

    assert result["success"] is False
    assert result["failure_code"] == "UPSTREAM_SCHEMA_DRIFT"
    assert result["quality_status"] == "error"


def test_fetch_cni_daily_invalid_param():
    result = fetch_cni_daily.fetch_cni_index_daily("399001", "2026/01/01", "20260110")
    assert result["success"] is False
    assert result["failure_code"] == "INVALID_PARAM"
