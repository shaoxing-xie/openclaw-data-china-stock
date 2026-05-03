from __future__ import annotations

from plugins.utils.plugin_data_registry import (
    get_source_chain,
    list_factor_ids,
    list_screenable_factor_ids,
    load_registry,
    reorder_tagged_providers_by_catalog,
    resolve_registry_path,
)


def test_load_registry_has_factors_and_chains():
    r = load_registry()
    assert r.get("schema_version")
    assert isinstance(r.get("factors"), list)
    assert isinstance(r.get("source_chains"), dict)
    assert "global_index_spot" in r["source_chains"]
    assert "factor_registry.yaml" in str(r.get("registry_path") or "")


def test_resolve_registry_path_prefers_factor_registry():
    p = resolve_registry_path()
    assert p.name == "factor_registry.yaml"


def test_list_factor_ids():
    ids = list_factor_ids()
    assert "reversal_5d" in ids
    assert "pe_ttm" in ids


def test_list_screenable_excludes_unimplemented():
    ids = list_screenable_factor_ids()
    assert "pe_ttm" not in ids
    assert "pb_mrq" not in ids
    assert set(ids) == {"reversal_5d", "fund_flow_3d", "sector_momentum_5d"}


def test_get_source_chain():
    ch = get_source_chain("a_share_fund_flow")
    assert "provider_tags" in ch


def test_reorder_tagged_providers_by_catalog_fund_flow():
    tagged = [("ths", 1), ("eastmoney", 2)]
    out = reorder_tagged_providers_by_catalog("a_share_fund_flow", tagged)
    tags = [t for t, _ in out]
    assert tags[0] == "ths"
    assert tags[1] == "eastmoney"
