"""
申万一级行业名（展示名）与股票六码映射 — 数据来自 `config/sw_industry_level1_mapping.json`。

运行 `scripts/update_sw_industry_level1_mapping.py` 刷新（默认：乐咕乐股 `sw_index_first_info` + `sw_index_third_cons`；可选环境变量 `SW_MAP_USE_EM_SPOT=1` 走东财快照）。公开接口，非投资建议。
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_sw_level1_mapping() -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    返回 (code -> 申万一级行业名), meta（version, mapping_version, as_of 等）。
    文件不存在或为空时返回 ({}, {})。
    """
    p = _repo_root() / "config" / "sw_industry_level1_mapping.json"
    if not p.is_file():
        return {}, {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.warning("sw mapping load failed: %s", e)
        return {}, {}
    if not isinstance(raw, dict):
        return {}, {}
    m = raw.get("code_to_sw_name") or raw.get("code_to_industry")
    if not isinstance(m, dict):
        m = {}
    norm = {str(k).zfill(6)[:6]: str(v).strip() for k, v in m.items() if k and v}
    meta = {k: v for k, v in raw.items() if k != "code_to_sw_name" and k != "code_to_industry"}
    return norm, meta


def industry_for_code(code: str) -> Optional[str]:
    c = str(code or "").strip().zfill(6)[:6]
    if len(c) != 6 or not c.isdigit():
        return None
    m, _ = load_sw_level1_mapping()
    return m.get(c) or None


def mapping_stats(codes: list[str]) -> Tuple[int, int, float]:
    """命中数、总数、覆盖率。"""
    m, _ = load_sw_level1_mapping()
    if not codes:
        return 0, 0, 0.0
    hit = sum(1 for c in codes if m.get(str(c).zfill(6)[:6]))
    return hit, len(codes), hit / max(len(codes), 1)
