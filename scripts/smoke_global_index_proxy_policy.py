#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "plugins") not in sys.path:
    sys.path.insert(0, str(ROOT / "plugins"))

from plugins.data_collection.index.fetch_global import tool_fetch_global_index_spot
from plugins.data_collection.index.fetch_global_hist_sina import tool_fetch_global_index_hist_sina


def main() -> int:
    spot = tool_fetch_global_index_spot(index_codes="^DJI,^IXIC,^GSPC")
    hist = tool_fetch_global_index_hist_sina(symbol="DJI", limit=5)
    out = {
        "spot_success": bool(spot.get("success")),
        "spot_source_id": spot.get("source_id"),
        "spot_attempts": spot.get("attempts"),
        "hist_success": bool(hist.get("success")),
        "hist_source_id": hist.get("source_id"),
        "hist_source": hist.get("source"),
    }
    print(json.dumps(out, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
