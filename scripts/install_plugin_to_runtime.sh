#!/usr/bin/env bash
# Sync openclaw-data-china-stock development tree into OpenClaw runtime extensions directory.
# After sync, run register_openclaw_dev.py from the *destination* (or set OPENCLAW_DATA_CHINA_STOCK_ROOT).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "${SCRIPT_DIR}/.." && pwd)"
DST="${OPENCLAW_DATA_CHINA_STOCK_RUNTIME:-${HOME}/.openclaw/extensions/openclaw-data-china-stock}"

usage() {
  echo "Usage: OPENCLAW_DATA_CHINA_STOCK_RUNTIME=<dir> $0"
  echo "  Default DST: ~/.openclaw/extensions/openclaw-data-china-stock"
  echo "  Excludes: .git .venv __pycache__ .pytest_cache *.pyc node_modules .tgz"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

mkdir -p "$(dirname "$DST")"
echo "rsync ${SRC}/ -> ${DST}/"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '*.pyc' \
  --exclude 'node_modules/' \
  --exclude '.tgz' \
  --exclude '*.parquet' \
  "${SRC}/" "${DST}/"

echo ""
echo "Done. Next:"
echo "  1) Use the same Python venv for tools (recommended):"
echo "       export OPENCLAW_DATA_CHINA_STOCK_PYTHON=\"${DST}/.venv/bin/python\""
echo "     Or keep a dedicated venv and point OPENCLAW_DATA_CHINA_STOCK_PYTHON to it."
echo "  2) Register plugin + skills against runtime tree:"
echo "       OPENCLAW_DATA_CHINA_STOCK_ROOT=\"${DST}\" python3 \"${DST}/scripts/register_openclaw_dev.py\""
echo "  3) Restart OpenClaw Gateway / doctor check."
