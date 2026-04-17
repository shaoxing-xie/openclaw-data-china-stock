"""Constants and routing for macro data tools."""

from __future__ import annotations

from typing import Dict, Tuple


# dataset -> (akshare function, source tag, unit)
MACRO_DATASET_MAP: Dict[str, Tuple[str, str, str]] = {
    # PMI / boom
    "pmi_official": ("macro_china_pmi", "NBS", "index"),
    "pmi_caixin_manufacturing": ("macro_china_cx_pmi_yearly", "Caixin", "index"),
    "pmi_caixin_services": ("macro_china_cx_services_pmi_yearly", "Caixin", "index"),
    "enterprise_boom": ("macro_china_enterprise_boom_index", "NBS", "index"),
    "lpi": ("macro_china_lpi_index", "CFLP", "index"),
    # inflation
    "cpi": ("macro_china_cpi", "NBS", "pct"),
    "ppi": ("macro_china_ppi", "NBS", "pct"),
    # money / credit
    "m2_yoy": ("macro_china_m2_yearly", "PBOC", "pct"),
    "social_financing": ("macro_china_shrzgm", "PBOC", "billion_cny"),
    "new_credit": ("macro_china_new_financial_credit", "PBOC", "billion_cny"),
    "lpr": ("macro_china_lpr", "PBOC", "pct"),
    "fx_reserves": ("macro_china_fx_reserves_yearly", "SAFE", "usd_100m"),
    # growth
    "gdp": ("macro_china_gdp", "NBS", "pct"),
    "industrial_value_added": ("macro_china_gyzjz", "NBS", "pct"),
    "fixed_asset_investment": ("macro_china_gdzctz", "NBS", "pct"),
    "leverage": ("macro_cnbs", "NBS", "pct"),
    # external
    "exports_imports": ("macro_china_hgjck", "GACC", "pct"),
    "trade_balance_usd": ("macro_china_trade_balance", "GACC", "usd_100m"),
    "exports_yoy_usd": ("macro_china_exports_yoy", "GACC", "pct"),
    # others
    "urban_unemployment": ("macro_china_urban_unemployment", "NBS", "pct"),
    "tax_receipts": ("macro_china_national_tax_receipts", "MOF", "billion_cny"),
}


TOOL_TO_DATASET: Dict[str, str] = {
    "tool_fetch_macro_pmi": "pmi_official",
    "tool_fetch_macro_cx_pmi": "pmi_caixin_manufacturing",
    "tool_fetch_macro_cx_services_pmi": "pmi_caixin_services",
    "tool_fetch_macro_enterprise_boom": "enterprise_boom",
    "tool_fetch_macro_lpi": "lpi",
    "tool_fetch_macro_cpi": "cpi",
    "tool_fetch_macro_ppi": "ppi",
    "tool_fetch_macro_m2": "m2_yoy",
    "tool_fetch_macro_social_financing": "social_financing",
    "tool_fetch_macro_new_credit": "new_credit",
    "tool_fetch_macro_lpr": "lpr",
    "tool_fetch_macro_fx_reserves": "fx_reserves",
    "tool_fetch_macro_gdp": "gdp",
    "tool_fetch_macro_industrial_value": "industrial_value_added",
    "tool_fetch_macro_fixed_asset": "fixed_asset_investment",
    "tool_fetch_macro_leverage": "leverage",
    "tool_fetch_macro_exports_imports": "exports_imports",
    "tool_fetch_macro_trade_balance": "trade_balance_usd",
    "tool_fetch_macro_exports_yoy": "exports_yoy_usd",
    "tool_fetch_macro_unemployment": "urban_unemployment",
    "tool_fetch_macro_tax_receipts": "tax_receipts",
}

# Canonical tool groups for China Macro Analyst.
PRIMARY_MACRO_TOOLS = (
    "tool_fetch_macro_data",
    "tool_fetch_macro_snapshot",
)

ANALYST_COMPAT_TOOLS = tuple(sorted(TOOL_TO_DATASET.keys()))

# Legacy macro-prefixed tools that are out of analyst scope but kept for compatibility.
ADJACENT_LEGACY_MACRO_TOOLS = (
    "tool_fetch_macro_commodities",
)


DEFAULT_DQ_POLICY = {
    "staleness_days_warn": 45,
    "staleness_days_error": 120,
}

