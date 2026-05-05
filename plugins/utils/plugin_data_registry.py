"""
Load ``config/factor_registry.yaml`` (preferred) or legacy ``plugin_data_registry.yaml``.

Read-only; safe for import-time use. Paths resolved from repo root (parent of config/).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple, TypeVar

import yaml

T = TypeVar("T")

_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_PRIORITY_PATH = _ROOT / "config" / "source_priority.yaml"
_REGISTRY_CANDIDATES = (
    _ROOT / "config" / "factor_registry.yaml",
    _ROOT / "config" / "plugin_data_registry.yaml",
)

_FALLBACK_SCREENABLE = ("reversal_5d", "fund_flow_3d", "sector_momentum_5d")


def resolve_registry_path() -> Path:
    for p in _REGISTRY_CANDIDATES:
        if p.is_file():
            return p
    return _REGISTRY_CANDIDATES[0]


@lru_cache(maxsize=4)
def load_registry(path: str | None = None) -> Dict[str, Any]:
    p = Path(path) if path else resolve_registry_path()
    if not p.is_file():
        return {
            "schema_version": "0.0.0",
            "factors": [],
            "source_chains": {},
            "_error": f"missing_registry:{p}",
            "registry_path": str(p),
        }
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {
            "schema_version": "0.0.0",
            "factors": [],
            "source_chains": {},
            "_error": "invalid_yaml_root",
            "registry_path": str(p),
        }
    factors = raw.get("factors") or []
    chains = raw.get("source_chains") or {}
    if not isinstance(factors, list):
        factors = []
    if not isinstance(chains, dict):
        chains = {}
    return {
        "schema_version": str(raw.get("schema_version") or "1.0.0"),
        "factors": factors,
        "source_chains": chains,
        "registry_note": raw.get("registry_note"),
        "registry_path": str(p.resolve()),
    }


def list_factor_ids() -> List[str]:
    out: List[str] = []
    for row in load_registry().get("factors") or []:
        if isinstance(row, dict) and row.get("factor_id"):
            out.append(str(row["factor_id"]))
    return out


def list_screenable_factor_ids() -> List[str]:
    """
    Factors that ``tool_screen_equity_factors`` currently implements.

    Excludes rows with ``implemented: false`` and rows whose ``source_tool`` is not
    ``tool_screen_equity_factors``. Falls back to built-in triple if none match.
    """
    out: List[str] = []
    for row in load_registry().get("factors") or []:
        if not isinstance(row, dict):
            continue
        if row.get("implemented") is False:
            continue
        tool = str(row.get("source_tool") or "tool_screen_equity_factors")
        if tool != "tool_screen_equity_factors":
            continue
        fid = row.get("factor_id")
        if fid:
            out.append(str(fid))
    return out if out else list(_FALLBACK_SCREENABLE)


def get_source_chain(dataset_key: str) -> Dict[str, Any]:
    chains = load_registry().get("source_chains") or {}
    if dataset_key in chains and isinstance(chains[dataset_key], dict):
        return dict(chains[dataset_key])
    return {}


_GLOBAL_SPOT_IDS = frozenset({"yfinance", "fmp", "sina"})
_CATALOG_NON_ORDER_TAGS = frozenset({"cache", "akshare"})


@lru_cache(maxsize=2)
def _load_source_priority_config() -> Dict[str, Any]:
    if not _SOURCE_PRIORITY_PATH.is_file():
        return {"dynamic_priority_enabled": False, "adjustment_mode": "tie_break_only"}
    raw = yaml.safe_load(_SOURCE_PRIORITY_PATH.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {"dynamic_priority_enabled": False}


def _rollup_latest_success_rates(provider_ids: frozenset[str]) -> Dict[str, float]:
    """
    读取 source_health 的 probe rollup（近 N 日），取各 source 序列最后一日的 success_rate。
    """
    from plugins.utils.source_health import rollup_path

    path = rollup_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    series = data.get("series") or {}
    out: Dict[str, float] = {}
    for sid in provider_ids:
        arr = series.get(sid)
        if isinstance(arr, list) and arr:
            last = arr[-1]
            if isinstance(last, dict):
                sr = last.get("success_rate")
                if sr is not None:
                    try:
                        out[sid] = float(sr)
                    except (TypeError, ValueError):
                        pass
    return out


def _append_dynamic_priority_audit(record: Dict[str, Any]) -> None:
    path = _ROOT / "data" / "meta" / "dynamic_priority_audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _apply_dynamic_tie_break_global_spot(
    merged: List[str], meta: Dict[str, Any]
) -> Tuple[List[str], Dict[str, Any]]:
    cfg = _load_source_priority_config()
    enabled = bool(cfg.get("dynamic_priority_enabled", False))
    mode = str(cfg.get("adjustment_mode") or "tie_break_only")
    dp = meta.setdefault("dynamic_priority", {})
    dp.update({"enabled": enabled, "adjustment_mode": mode})
    if not enabled or mode != "tie_break_only":
        return merged, meta
    scores = _rollup_latest_success_rates(_GLOBAL_SPOT_IDS)
    before = list(merged)
    order_idx = {sid: i for i, sid in enumerate(merged)}
    new_merged = sorted(merged, key=lambda sid: (-scores.get(sid, 0.5), order_idx[sid]))
    dp["scores_used"] = scores
    if new_merged != before:
        dp["applied"] = True
        dp["before"] = before
        dp["after"] = list(new_merged)
        _append_dynamic_priority_audit(
            {
                "dataset_id": "global_index_spot",
                "before": before,
                "after": list(new_merged),
                "scores": scores,
            }
        )
        return new_merged, meta
    dp["applied"] = False
    return merged, meta


def merge_global_index_spot_priority(config_priority: List[str]) -> Tuple[List[str], Dict[str, Any]]:
    """
    Merge ``data_sources.global_index.latest.priority`` with ``source_chains.global_index_spot``.

    Catalog defines relative order among providers that exist in **both** catalog and config.
    Config entries not listed in catalog are appended after, preserving config relative order.
    Unknown catalog tags (e.g. cache) are ignored for this fetcher.
    """
    raw = [str(x).lower().strip() for x in (get_source_chain("global_index_spot").get("provider_tags") or [])]
    catalog = [x for x in raw if x in _GLOBAL_SPOT_IDS]
    meta: Dict[str, Any] = {
        "dataset_id": "global_index_spot",
        "catalog_provider_tags_raw": raw,
        "catalog_provider_tags_effective": list(catalog),
    }
    base = [str(p).lower().strip() for p in (config_priority or []) if isinstance(p, str)]
    priority = [p for p in base if p in _GLOBAL_SPOT_IDS]
    if not priority:
        priority = ["yfinance", "fmp", "sina"]
    if not catalog:
        meta["merge_mode"] = "config_only_empty_catalog"
        merged = list(dict.fromkeys(priority))
        return _apply_dynamic_tie_break_global_spot(merged, meta)

    allowed = set(priority)
    merged = []
    for t in catalog:
        if t in allowed and t not in merged:
            merged.append(t)
    for t in priority:
        if t not in merged:
            merged.append(t)
    meta["merge_mode"] = "catalog_first_then_config_remainder"
    return _apply_dynamic_tie_break_global_spot(merged, meta)


def reorder_tagged_providers_by_catalog(dataset_key: str, tagged: List[Tuple[str, T]]) -> List[Tuple[str, T]]:
    """
    Reorder ``(provider_tag, item)`` tuples to follow ``source_chains[dataset_key].provider_tags``.

    Tags not present in ``tagged`` are skipped. Tags in ``tagged`` but not in catalog keep their
    relative order after catalog-matched entries. Tags like ``cache`` in YAML are ignored.
    """
    raw = [str(x).lower().strip() for x in (get_source_chain(dataset_key).get("provider_tags") or [])]
    tags = [x for x in raw if x not in _CATALOG_NON_ORDER_TAGS]
    if not tags:
        return list(tagged)
    used: set[int] = set()
    out: List[Tuple[str, T]] = []
    for ct in tags:
        for i, (tag, item) in enumerate(tagged):
            if tag == ct and i not in used:
                out.append((tag, item))
                used.add(i)
                break
    for i, pair in enumerate(tagged):
        if i not in used:
            out.append(pair)
            used.add(i)
    return out
