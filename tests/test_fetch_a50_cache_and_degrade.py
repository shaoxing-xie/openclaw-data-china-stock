import pandas as pd

from plugins.data_collection.futures import fetch_a50


def test_a50_spot_cache_hit(monkeypatch):
    fetch_a50._save_a50_spot_cache(
        {
            "code": "CN00Y",
            "name": "A50",
            "current_price": 12000.0,
            "change_pct": 0.1,
            "volume": 1000.0,
            "timestamp": "2026-01-01 10:00:00",
        }
    )
    monkeypatch.setattr(fetch_a50, "AKSHARE_AVAILABLE", True)
    monkeypatch.setattr(fetch_a50, "ak", object())

    result = fetch_a50.fetch_a50_data(data_type="spot", use_cache=True)

    assert result["success"] is True
    assert result["cache_hit"] is True
    assert result["source_stage"] == "cache"
    assert isinstance(result["cache_age_ms"], int)


def test_a50_hist_only_degraded_when_spot_missing(monkeypatch):
    monkeypatch.setattr(fetch_a50, "AKSHARE_AVAILABLE", True)

    class DummyAK:
        @staticmethod
        def futures_global_spot_em():
            raise RuntimeError("upstream timeout")

        @staticmethod
        def futures_foreign_hist(symbol):
            return pd.DataFrame(
                {
                    "date": ["2026-01-01", "2026-01-02"],
                    "open": [12000, 12010],
                    "close": [12020, 12030],
                    "high": [12030, 12040],
                    "low": [11990, 12000],
                    "volume": [100, 120],
                }
            )

    monkeypatch.setattr(fetch_a50, "ak", DummyAK)
    monkeypatch.setattr(fetch_a50, "CACHE_AVAILABLE", False)

    result = fetch_a50.fetch_a50_data(
        data_type="both",
        start_date="20260101",
        end_date="20260102",
        use_cache=False,
    )

    assert result["success"] is True
    assert result["spot_data"] is None
    assert result["hist_data"] is not None
    assert result["quality"] == "degraded"
    assert result["degraded_reason"] == "SPOT_UNAVAILABLE_HIST_ONLY"
