#!/usr/bin/env python3
"""
构建「沪深京 A 股六码 → 申万一级行业名称」静态表，写入 config/sw_industry_level1_mapping.json。

优先路径（推荐）：
  AkShare `sw_index_first_info`（申万一级行业列表）+
  `sw_index_third_cons`（乐咕乐股行业成份；参数为一级行业代码如 801010.SI 即可拉取该级全部成份）。
  不依赖东财 push2 全市场分页，可避免 RemoteDisconnected。

可选旧路径（环境变量 SW_MAP_USE_EM_SPOT=1）：
  尝试 `stock_zh_a_spot_em`（当前 AkShare 实现未必含「行业」列，且易被对端断开）。

用法（插件主仓根目录）:
  PYTHONPATH=. .venv/bin/python scripts/update_sw_industry_level1_mapping.py
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict

ROOT = Path(__file__).resolve().parents[1]


def _norm_a_code(raw: str) -> str | None:
    """000019.SZ / 600000.SH / 600000 -> 六位数字码。"""
    s = str(raw or "").strip().upper()
    if not s:
        return None
    if "." in s:
        s = s.split(".", 1)[0]
    s = s.zfill(6)[:6]
    return s if len(s) == 6 and s.isdigit() else None


def _retry_call(
    fn: Callable[[], Any],
    *,
    attempts: int = 5,
    base_sleep: float = 1.5,
    label: str = "",
) -> Any:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if i == attempts - 1:
                break
            delay = base_sleep * (2**i) + random.uniform(0, 0.5)
            print(f"{label}retry {i + 1}/{attempts} after {delay:.1f}s: {e}", file=sys.stderr)
            time.sleep(delay)
    assert last is not None
    raise last


def _build_from_legulegu() -> Dict[str, str]:
    import akshare as ak

    first = _retry_call(ak.sw_index_first_info, label="sw_index_first_info ")
    if first is None or first.empty:
        raise RuntimeError("sw_index_first_info empty")

    m: dict[str, str] = {}
    pause = float(os.environ.get("SW_MAP_INTER_REQUEST_SLEEP", "0.35"))

    for _, row in first.iterrows():
        ind_code = str(row.get("行业代码") or "").strip()
        ind_name = str(row.get("行业名称") or "").strip()
        if not ind_code or not ind_name:
            continue

        def _fetch_cons() -> Any:
            return ak.sw_index_third_cons(symbol=ind_code)

        try:
            cons = _retry_call(_fetch_cons, attempts=4, base_sleep=2.0, label=f"{ind_code} ")
        except Exception as e:  # noqa: BLE001
            print(f"skip industry {ind_code} ({ind_name}): {e}", file=sys.stderr)
            time.sleep(pause)
            continue

        if cons is None or cons.empty or "股票代码" not in cons.columns:
            time.sleep(pause)
            continue

        for _, r2 in cons.iterrows():
            code = _norm_a_code(r2.get("股票代码"))
            if not code:
                continue
            # 成份表内「申万1级」应与 ind_name 一致；以 first_info 名为准
            m[code] = ind_name

        time.sleep(pause)

    return m


def _build_from_em_spot() -> Dict[str, str]:
    """旧接口：东财 A 股快照（可能无「行业」列或连接不稳定）。"""
    import akshare as ak

    df = _retry_call(ak.stock_zh_a_spot_em, attempts=6, base_sleep=2.0, label="stock_zh_a_spot_em ")
    if df is None or df.empty:
        raise RuntimeError("empty dataframe")

    code_col = "代码" if "代码" in df.columns else None
    ind_col = "行业" if "行业" in df.columns else None
    if not code_col:
        for c in df.columns:
            if "代码" in str(c):
                code_col = c
                break
    if not ind_col:
        for c in df.columns:
            if "行业" in str(c):
                ind_col = c
                break
    if not code_col or not ind_col:
        raise RuntimeError(
            f"stock_zh_a_spot_em has no 行业 column; columns={list(df.columns)}"
        )

    m: dict[str, str] = {}
    for _, row in df.iterrows():
        code = _norm_a_code(row.get(code_col))
        ind = str(row.get(ind_col) or "").strip()
        if code and ind:
            m[code] = ind
    return m


def main() -> int:
    try:
        import akshare as ak  # noqa: F401
    except ImportError:
        print("需要安装 akshare", file=sys.stderr)
        return 1

    use_em = os.environ.get("SW_MAP_USE_EM_SPOT", "").strip() in ("1", "true", "yes")
    try:
        if use_em:
            m = _build_from_em_spot()
            source = "akshare.stock_zh_a_spot_em"
        else:
            m = _build_from_legulegu()
            source = "akshare.sw_index_first_info+sw_index_third_cons (legulegu)"
    except Exception as e:  # noqa: BLE001
        print(f"build failed: {e}", file=sys.stderr)
        return 1

    if not m:
        print("empty mapping", file=sys.stderr)
        return 1

    out_path = ROOT / "config" / "sw_industry_level1_mapping.json"
    payload = {
        "version": 1,
        "mapping_version": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": source,
        "code_to_sw_name": m,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": True, "path": str(out_path), "count": len(m)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
