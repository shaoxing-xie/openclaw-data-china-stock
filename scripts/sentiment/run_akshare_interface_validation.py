#!/usr/bin/env python3
from __future__ import annotations

import inspect
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

import pandas as pd

try:
    import akshare as ak
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f"akshare import failed: {exc}")


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "docs" / "sentiment" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _safe_count(df: Any) -> int:
    if isinstance(df, pd.DataFrame):
        return int(len(df))
    return 0


def _safe_columns(df: Any) -> List[str]:
    if isinstance(df, pd.DataFrame):
        return [str(c) for c in df.columns[:20]]
    return []


def _run_case(name: str, fn: Callable[[], Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        data = fn()
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "name": name,
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "record_count": _safe_count(data),
            "columns_sample": _safe_columns(data),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "name": name,
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "record_count": 0,
            "columns_sample": [],
            "error": str(exc)[:300],
        }


def main() -> None:
    today = datetime.now().strftime("%Y%m%d")
    cases: List[Dict[str, Any]] = []
    api_meta: Dict[str, str] = {}
    signatures = [
        "stock_zt_pool_em",
        "stock_market_fund_flow",
        "stock_sector_fund_flow_rank",
        "stock_individual_fund_flow_rank",
        "stock_hsgt_fund_flow_summary_em",
        "stock_sector_spot",
        "stock_board_industry_name_em",
    ]
    for f in signatures:
        try:
            api_meta[f] = str(inspect.signature(getattr(ak, f)))
        except Exception as exc:  # noqa: BLE001
            api_meta[f] = f"signature_error: {exc}"

    cases.append(_run_case("stock_zt_pool_em", lambda: ak.stock_zt_pool_em(today)))
    cases.append(_run_case("stock_market_fund_flow", lambda: ak.stock_market_fund_flow()))
    cases.append(
        _run_case(
            "stock_sector_fund_flow_rank",
            lambda: ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流"),
        )
    )
    cases.append(
        _run_case(
            "stock_individual_fund_flow_rank",
            lambda: ak.stock_individual_fund_flow_rank(indicator="今日"),
        )
    )
    cases.append(_run_case("stock_hsgt_fund_flow_summary_em", lambda: ak.stock_hsgt_fund_flow_summary_em()))
    cases.append(_run_case("stock_sector_spot_行业", lambda: ak.stock_sector_spot(indicator="行业")))
    cases.append(_run_case("stock_board_industry_name_em", lambda: ak.stock_board_industry_name_em()))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {"generated_at": now, "api_signatures": api_meta, "cases": cases}
    json_path = REPORT_DIR / "akshare_interface_validation_latest.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# AKShare Interface Validation Report",
        "",
        f"- generated_at: {now}",
        "",
        "## Signatures",
        "",
    ]
    for k, v in api_meta.items():
        lines.append(f"- `{k}`: `{v}`")
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    lines.append("| interface | ok | elapsed_ms | record_count | columns_sample | error |")
    lines.append("|---|---:|---:|---:|---|---|")
    for c in cases:
        cols = ", ".join(c["columns_sample"][:6])
        err = (c["error"] or "").replace("|", "/")
        lines.append(f"| {c['name']} | {int(c['ok'])} | {c['elapsed_ms']} | {c['record_count']} | {cols} | {err} |")
    md_path = REPORT_DIR / "akshare_interface_validation_latest.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote: {json_path}")
    print(f"wrote: {md_path}")


if __name__ == "__main__":
    main()
