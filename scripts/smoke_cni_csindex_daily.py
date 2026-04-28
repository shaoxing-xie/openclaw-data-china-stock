#!/usr/bin/env python3
"""
Smoke test for CNI + CSIndex daily collectors.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from plugins.data_collection.index.fetch_cni_daily import tool_fetch_cni_index_daily
from plugins.data_collection.index.fetch_csindex_daily import tool_fetch_csindex_index_daily


def _date_range() -> tuple[str, str]:
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=10)
    return start_dt.strftime("%Y%m%d"), end_dt.strftime("%Y%m%d")


def main() -> None:
    start_date, end_date = _date_range()
    cni_result = tool_fetch_cni_index_daily(symbol="399001", start_date=start_date, end_date=end_date)
    csindex_result = tool_fetch_csindex_index_daily(symbol="000300", start_date=start_date, end_date=end_date)

    summary = {
        "success": bool(cni_result.get("success")) and bool(csindex_result.get("success")),
        "cni": {
            "success": cni_result.get("success"),
            "count": cni_result.get("count"),
            "quality_status": cni_result.get("quality_status"),
            "failure_code": cni_result.get("failure_code", ""),
        },
        "csindex": {
            "success": csindex_result.get("success"),
            "count": csindex_result.get("count"),
            "quality_status": csindex_result.get("quality_status"),
            "failure_code": csindex_result.get("failure_code", ""),
        },
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
