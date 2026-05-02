#!/usr/bin/env python3
"""
Validate plugins/config sector_etf_mapping.yaml: structure, unique ETF codes, required fields.

Exit 0 on success; non-zero on validation errors (P2 mapping discipline minimal check).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "config" / "sector_etf_mapping.yaml"
    if not path.is_file():
        print(json.dumps({"ok": False, "message": "mapping_missing", "path": str(path)}))
        return 1
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        print(json.dumps({"ok": False, "message": "root_not_object"}))
        return 1
    sectors = raw.get("sectors")
    if not isinstance(sectors, list) or not sectors:
        print(json.dumps({"ok": False, "message": "sectors_empty"}))
        return 1
    codes: list[str] = []
    errors: list[str] = []
    for i, s in enumerate(sectors):
        if not isinstance(s, dict):
            errors.append(f"sector[{i}]_not_object")
            continue
        for k in ("sector_name", "etf_code", "etf_name"):
            if not str(s.get(k) or "").strip():
                errors.append(f"sector[{i}]_missing_{k}")
        c = str(s.get("etf_code") or "").strip()
        if c:
            codes.append(c)
    dup = sorted({c for c in codes if codes.count(c) > 1})
    if dup:
        errors.append(f"duplicate_etf_codes:{dup}")
    print(json.dumps({"ok": not errors, "count": len(sectors), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
