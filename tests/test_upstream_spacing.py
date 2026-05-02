from plugins.utils.upstream_spacing import limit_up_chain_spacing_seconds


def test_limit_up_spacing_reads_nested_config(monkeypatch):
    monkeypatch.delenv("OPENCLAW_LIMIT_UP_CHAIN_SPACING_SECONDS", raising=False)
    cfg = {"data_sources": {"limit_up": {"upstream_chain_spacing_seconds": 0.12}}}
    assert limit_up_chain_spacing_seconds(cfg) == 0.12


def test_limit_up_spacing_falls_back_to_intraday_tool(monkeypatch):
    monkeypatch.delenv("OPENCLAW_LIMIT_UP_CHAIN_SPACING_SECONDS", raising=False)
    cfg = {"data_sources": {"limit_up": {}, "intraday_tool_spacing_seconds": 0.44}}
    assert limit_up_chain_spacing_seconds(cfg) == 0.44


def test_limit_up_spacing_env_override(monkeypatch):
    monkeypatch.setenv("OPENCLAW_LIMIT_UP_CHAIN_SPACING_SECONDS", "0.01")
    assert limit_up_chain_spacing_seconds({"data_sources": {}}) == 0.01
