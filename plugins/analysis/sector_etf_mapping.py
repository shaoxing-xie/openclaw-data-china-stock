from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass(frozen=True)
class SectorEtfMapping:
    sector_name: str
    index_code: str
    etf_code: str
    etf_name: str
    min_liquidity: float
    last_verified: str


_CACHE: Optional[List[SectorEtfMapping]] = None


def _config_path() -> Path:
    # repo_root/plugins/analysis -> repo_root
    return Path(__file__).resolve().parents[2] / "config" / "sector_etf_mapping.yaml"


def load_sector_etf_mappings(*, refresh: bool = False) -> List[SectorEtfMapping]:
    """
    Load sector->ETF mapping from config.

    This file is intended to be maintained without code changes.
    """
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE

    p = _config_path()
    if not p.exists():
        _CACHE = []
        return _CACHE

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    rows = raw.get("sectors") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        _CACHE = []
        return _CACHE

    out: List[SectorEtfMapping] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        sector_name = str(r.get("sector_name") or "").strip()
        etf_code = str(r.get("etf_code") or "").strip()
        if not sector_name or not etf_code:
            continue
        out.append(
            SectorEtfMapping(
                sector_name=sector_name,
                index_code=str(r.get("index_code") or "").strip(),
                etf_code=etf_code,
                etf_name=str(r.get("etf_name") or "").strip(),
                min_liquidity=float(r.get("min_liquidity") or 0.0),
                last_verified=str(r.get("last_verified") or "").strip(),
            )
        )
    _CACHE = out
    return out


def get_etf_codes_from_mapping(*, min_coverage: int = 20) -> Dict[str, Any]:
    mappings = load_sector_etf_mappings()
    etfs = [m.etf_code for m in mappings if m.etf_code]
    ok = len(etfs) >= int(min_coverage or 0)
    return {
        "ok": ok,
        "count": len(etfs),
        "min_coverage": int(min_coverage or 0),
        "etf_codes": etfs,
        "sectors": [m.sector_name for m in mappings],
        "config_path": str(_config_path()),
    }


def get_sector_by_etf(etf_code: str) -> Optional[SectorEtfMapping]:
    code = str(etf_code or "").strip()
    if not code:
        return None
    for m in load_sector_etf_mappings():
        if m.etf_code == code:
            return m
    return None

