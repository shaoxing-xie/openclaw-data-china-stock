# openclaw-data-china-stock

Market-data infrastructure for OpenClaw, covering A-share, ETF, index, option, fund-flow, technical indicators, and macro datasets.

[![GitHub release](https://img.shields.io/github/v/release/shaoxing-xie/openclaw-data-china-stock)](https://github.com/shaoxing-xie/openclaw-data-china-stock/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Plugin-blue)](https://openclaw.ai/)

One-line summary: a unified plugin layer that combines market data retrieval, a 58-indicator engine, and macro analysis endpoints for OpenClaw agents.

## Why this plugin

In China-market automation workflows, common engineering issues are:

- unstable upstream APIs and expensive maintenance
- indicator implementation drift across environments
- output mismatch against local charting conventions
- fragmented macro data collection and normalization
- disconnected data/analysis/agent execution pipelines

This plugin addresses these issues with a single, reusable tool surface.

## Core capabilities

### 1) Unified market data retrieval

- primary entry: `tool_fetch_market_data` (`index` / `etf` / `stock` / `option`)
- cache read entry: `tool_read_market_data`
- A-share specialized tools: fund flow, screeners, pre-market/intraday views, valuation snapshot, sector heat, and more
- multi-source fallback and retry controls to reduce single-provider failure impact

### 2) Technical indicator engine (58 indicators)

- tool: `tool_calculate_technical_indicators`
- full P0/P1/P2 coverage (trend, momentum, volatility, candlestick patterns, statistics)
- engine order: `TA-Lib -> pandas-ta -> builtin`
- output modes: `append` / `standalone`
- structured errors: `VALIDATION_ERROR`, `UPSTREAM_EMPTY_DATA`, `UPSTREAM_FETCH_FAILED`, `RUNTIME_ERROR`

Details: `plugins/data_collection/technical_indicators/README.md`

### 3) Macro data layer (v0.4.0+)

- primary tools:
  - `tool_fetch_macro_data(dataset, latest_only, lookback, frequency)`
  - `tool_fetch_macro_snapshot(scope, include_quadrant)`
- compatibility tools: `tool_fetch_macro_*` for legacy workflows
- macro skill: `skills/china-macro-analyst/SKILL.md`
- macro docs:
  - `docs/macro/api_contract.md`
  - `docs/macro/error_codes.md`
  - `docs/macro/dq_policy.md`

### 4) Multi-factor equity screening (A-share)

- tool: `tool_screen_equity_factors` (`plugins/analysis/equity_factor_screening.py`; registered in manifest / `tool_runner`)
- batch: `tool_batch_fetch` whitelist includes this tool (`plugins/merged/tool_batch_fetch.py`)
- Shenwan L1 static mapping: `config/sw_industry_level1_mapping.json` ← `scripts/update_sw_industry_level1_mapping.py`
- schema / tests: `docs/schemas/tool_screen_equity_factors.schema.json`, `tests/test_tool_screen_equity_factors_contract.py`
- companion in **etf-options-ai-assistant**: nightly finalize / emergency pause tools and Skill `ota_equity_factor_screening_brief` (see that repo)

### 5) Agent-oriented integration

- unified routing through `config/tools_manifest.json` and `tool_runner.py`
- fast developer registration via `scripts/register_openclaw_dev.py` (symlinks skills such as `market-scanner`, `market-sentinel`, `fund-flow-analyst`, and others into the workspace)
- deterministic Python interpreter resolution for cross-environment deployment

## Quick start

Primary setup guide: `INSTALL.md` (source install, package install, env config, validation commands).

### Install from ClawHub

```bash
openclaw plugins install clawhub:@shaoxing-xie/openclaw-data-china-stock
```

If your OpenClaw CLI version does not support the `clawhub:` prefix, use:

```bash
openclaw plugins install @shaoxing-xie/openclaw-data-china-stock
```

### Install from source

```bash
cd /path/to/openclaw-data-china-stock
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

### Dev registration (recommended)

```bash
.venv/bin/python scripts/register_openclaw_dev.py
```

This script updates `~/.openclaw/openclaw.json` in append-only mode and exposes related skills to the OpenClaw workspace.

## Typical agent instructions

- "Fetch one-year daily data for 510300 and compute RSI, MACD, and Bollinger Bands."
- "Return today's strongest A-share sector by fund flow and the corresponding ETF."
- "Produce the latest macro snapshot and identify the Merrill-cycle quadrant."

## Documentation map

- installation and deployment: `INSTALL.md`
- indicator details: `plugins/data_collection/technical_indicators/README.md`
- macro skill: `skills/china-macro-analyst/SKILL.md`
- market sentiment aggregate skill: `skills/market-sentinel/SKILL.md`
- macro API / errors / data quality:
  - `docs/macro/api_contract.md`
  - `docs/macro/error_codes.md`
  - `docs/macro/dq_policy.md`
- release notes: `CHANGELOG.md`

## Testing

Full test suite:

```bash
python -m pytest -q tests/
```

Minimal critical-path tests:

```bash
python -m pytest -q tests/test_manifest_tool_map_parity.py tests/test_tool_runner_dispatch.py tests/test_technical_indicators_tool.py
```

## Operational notes

### Cache policy

Disk parquet writes are disabled by default (`data_cache.enabled=false`):

- reads from existing cache are allowed
- new parquet writes are skipped

Enable `data_cache.enabled=true` in `config.yaml` only when explicit local read/write caching is required.

### Return contract

Most tools return:

- `success`
- `data`
- `message`
- `source`

Some tools also include `count`, `timestamp`, `cache_hit`, `provider`, `fallback_route`, and `attempt_counts`.

## Contribution

Contributions are welcome via issues and pull requests:

- report problems / feature requests through [GitHub Issues](https://github.com/shaoxing-xie/openclaw-data-china-stock/issues)
- submit PRs based on `main`

## Disclaimer

This plugin provides data collection and technical research tooling only.  
It does not constitute investment advice.

## License

MIT

## Acknowledgement

The project builds on open-source ecosystem interfaces (including AKShare) for China-market data workflows.
