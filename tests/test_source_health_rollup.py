from __future__ import annotations

import json

import plugins.utils.source_health as sh


def test_write_probe_history_rollup_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sh, "_repo_root", lambda: tmp_path)
    out = sh.write_probe_history_rollup(days=7)
    assert out.is_file()
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc.get("_meta", {}).get("schema_name") == "source_health_history_rollup"
    assert doc.get("series") == {}


def test_append_probe_history_writes_jsonl_and_rollup(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sh, "_repo_root", lambda: tmp_path)
    rows = [{"source_id": "akshare", "ok": True, "detail": "x"}, {"source_id": "yfinance", "ok": False, "detail": "bad"}]
    sh.append_probe_history_sample(rows, "run-test-1")
    jlp = tmp_path / "data" / "logs" / "source_health_probe_history.jsonl"
    assert jlp.is_file()
    line = jlp.read_text(encoding="utf-8").strip().splitlines()[0]
    rec = json.loads(line)
    assert rec.get("sources_ok", {}).get("akshare") is True
    assert rec.get("sources_ok", {}).get("yfinance") is False
    rollup_p = tmp_path / "data" / "meta" / "source_health_history_rollup.json"
    assert rollup_p.is_file()
    rollup = json.loads(rollup_p.read_text(encoding="utf-8"))
    ser = rollup.get("series") or {}
    assert "akshare" in ser and "yfinance" in ser
