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
# `--delete` would remove extra files on DST; protect runtime `.venv` (created under DST, never synced from SRC).
rsync -a --delete \
  --filter 'protect .venv/' \
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
echo "  Note: SRC .venv is never synced; if you created \"${DST}/.venv\", it is preserved across reruns (rsync filter protect)."
echo "  1) Point tools to a Python venv (pick one):"
echo "     A) Recommended: use the dev repo venv (same deps as pytest):"
echo "        export OPENCLAW_DATA_CHINA_STOCK_PYTHON=\"${SRC}/.venv/bin/python\""
echo "     B) Or create a venv under runtime and install deps:"
echo "        python3 -m venv \"${DST}/.venv\" && \"${DST}/.venv/bin/pip\" install -r \"${DST}/requirements.txt\""
echo "        export OPENCLAW_DATA_CHINA_STOCK_PYTHON=\"${DST}/.venv/bin/python\""
echo "  2) Register plugin + skills against runtime tree:"
echo "       OPENCLAW_DATA_CHINA_STOCK_ROOT=\"${DST}\" python3 \"${DST}/scripts/register_openclaw_dev.py\""
echo "  3) Persist OPENCLAW_DATA_CHINA_STOCK_PYTHON in ~/.openclaw/.env (KEY=VALUE) or systemd/gateway env, then:"
echo "     Restart OpenClaw Gateway; run: openclaw plugins doctor"
