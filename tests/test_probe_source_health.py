from plugins.merged.probe_source_health import tool_probe_source_health


def test_tool_probe_source_health_dry_run():
    out = tool_probe_source_health(write_snapshot=False)
    assert out.get("success") is True
    assert isinstance(out.get("data"), list)


def test_tool_probe_source_health_writes_snapshot(tmp_path, monkeypatch):
    import plugins.utils.source_health as sh

    monkeypatch.setattr(sh, "_repo_root", lambda: tmp_path)
    out = tool_probe_source_health(source_ids="akshare", write_snapshot=True)
    assert out.get("success") is True
    snap = (tmp_path / "data" / "meta" / "source_health_snapshot.json").read_text(encoding="utf-8")
    assert "akshare" in snap
