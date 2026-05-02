from plugins.analysis.sector_etf_mapping import get_etf_codes_from_mapping, load_sector_etf_mappings


def test_sector_etf_mapping_has_minimum_coverage():
    info = get_etf_codes_from_mapping(min_coverage=20)
    assert info["ok"] is True
    assert info["count"] >= 20
    assert len(load_sector_etf_mappings()) >= 20

