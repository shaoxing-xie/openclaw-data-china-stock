#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DOCS = [
    "docs/sentiment/api_contract.md",
    "docs/sentiment/dq_policy.md",
    "docs/sentiment/error_codes.md",
    "docs/sentiment/akshare_interface_inventory.md",
    "docs/sentiment/akshare_interface_validation_report.md",
    "docs/sentiment/sentiment_data_object_call_chains.md",
]

TESTS = [
    "tests/test_a_share_fund_flow.py",
    "tests/test_fallback_logic.py",
]


def _run(cmd: list[str]) -> int:
    print("$", " ".join(cmd))
    p = subprocess.run(cmd, cwd=ROOT)
    return p.returncode


def main() -> int:
    missing = [p for p in REQUIRED_DOCS if not (ROOT / p).exists()]
    if missing:
        print("Missing docs:")
        for p in missing:
            print(" -", p)
        return 2

    rc = _run([sys.executable, "-m", "pytest", "-q", *TESTS])
    if rc != 0:
        return rc
    print("Stage gate check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
