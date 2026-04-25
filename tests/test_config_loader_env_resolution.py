from src import config_loader


def test_resolve_env_placeholder_full_value(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "demo-key")
    data = {"data_sources": {"global_index": {"latest": {"fmp": {"api_key": "${FMP_API_KEY}"}}}}}

    resolved = config_loader._resolve_env_placeholders(data)

    assert resolved["data_sources"]["global_index"]["latest"]["fmp"]["api_key"] == "demo-key"


def test_resolve_env_placeholder_embedded_value(monkeypatch):
    monkeypatch.setenv("API_HOST", "example.com")

    resolved = config_loader._resolve_env_placeholders({"url": "https://${API_HOST}/v1/quote"})

    assert resolved["url"] == "https://example.com/v1/quote"


def test_resolve_env_placeholder_missing_returns_none_for_full_token(monkeypatch):
    monkeypatch.delenv("UNSET_TOKEN", raising=False)

    resolved = config_loader._resolve_env_placeholders({"token": "${UNSET_TOKEN}"})

    assert resolved["token"] is None
