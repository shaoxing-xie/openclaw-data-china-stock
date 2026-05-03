from __future__ import annotations

from plugins.utils.attempts_rollup import (
    rollup_from_tool_response,
    summarize_attempts,
    tool_summarize_attempts,
)


def test_summarize_attempts():
    att = [
        {"source_id": "akshare", "source_stage": "primary"},
        {"source_id": "cache", "source_stage": "fallback"},
    ]
    s = summarize_attempts(att)
    assert s["total_events"] == 2
    assert s["by_source_id"]["akshare"] == 1


def test_rollup_from_tool_response():
    out = rollup_from_tool_response({"attempts": [{"source_id": "tushare"}], "success": True})
    assert out["by_source_id"]["tushare"] == 1


def test_tool_summarize_attempts():
    out = tool_summarize_attempts(attempts_json='[{"source_id":"akshare"},{"source_id":"akshare"}]')
    assert out["success"]
    assert out["data"]["by_source_id"]["akshare"] == 2
    assert out["_meta"]["schema_name"] == "attempts_summary_v1"


def test_tool_summarize_attempts_dataset_id():
    out = tool_summarize_attempts(
        attempts_json='[{"source_id":"yfinance"}]',
        dataset_id="global_index_spot",
    )
    assert out["data"].get("dataset_id") == "global_index_spot"
