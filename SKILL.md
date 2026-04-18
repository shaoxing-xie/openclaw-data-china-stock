---
name: openclaw-data-china-stock
description: A-share/ETF/Option market data collection plugin for OpenClaw.
tags: [data, china, etf, option, openclaw]
---

# OpenClaw Data China Stock

This plugin provides a ClawHub/OpenClaw compatible toolset for collecting A-share, ETF, and listed option data.

## Key tools

- `tool_fetch_market_data`: Cross-asset unified entry (recommended).
- `tool_fetch_index_data` / `tool_fetch_etf_data` / `tool_fetch_option_data`: Compatibility/alias unified entries.
- `tool_get_option_contracts`: Fetch option contracts by underlying.
- `tool_read_market_data` / `tool_read_*`: Read previously cached Parquet data (when enabled).

### Paired skill suite

- `skills/china-macro-analyst/SKILL.md`
- `skills/technical-analyst/SKILL.md`
- `skills/market-scanner/SKILL.md`
- `skills/market-sentinel/SKILL.md`
- `skills/fund-flow-analyst/SKILL.md`
- `skills/strategy-backtester/SKILL.md` (MVP mode)
- `skills/fundamental-analyst/SKILL.md`

### China macro analyst tools

- **Primary**: `tool_fetch_macro_data` / `tool_fetch_macro_snapshot`
- **Compatibility wrappers**: `tool_fetch_macro_*` (21 tools; kept for backward compatibility)
- **Skill**: `skills/china-macro-analyst/SKILL.md` (institutional 4-section narrative template; rules in `macro_config.yaml`)

### Fund-flow tools (pick one job, do not duplicate)

- **`tool_capital_flow`**: Single-stock **summary** for workflows that need `flow_judgement` / `risk_flags` style outputs (e.g. limit-up strategies).
- **`tool_fetch_a_share_fund_flow`**: **Tabular / ranking / history** for onshore A-share money flow (`query_kind` selects market/sector/stock tables, big deals, main-force ranks, sector drill-down). Uses Eastmoney/Tonghuashun-style AkShare routes with an explicit attempt chain; raw data is not investment advice.
- **`tool_fetch_northbound_flow`**: **Stock Connect northbound** flows (cross-border), separate from onshore A-share flow tools—keep narratives and citations distinct.
- **`tool_fetch_a_share_technical_screener`**: Tonghuashun-style **technical stock screeners** (new highs, consecutive up days, volume patterns, MA breakouts, etc.) via AkShare `stock_rank_*_ths`—**not** the same as locally computed MACD/RSI from OHLC (use `tool_stock_data_fetcher` / `tool_calculate_technical_indicators` for those).

## Safety and independence

The plugin is designed to run independently (no dependency on any other repository):

- It does not inject `~/.openclaw/.env`.
- It supports plugin-specific cache/data paths (configured inside the plugin).

## Why it helps retail users

- Unified cross-asset entry (`tool_fetch_market_data`) to reduce “tool switching” friction.
- Multi-source provider priority + automatic fallback to avoid single-provider outages breaking your workflow.
- Default read-only disk cache semantics (`data_cache.enabled=false`) to minimize local data pollution risk.

## Typical usage

Example: fetch A-share index daily historical data:

```yaml
tools:
  - name: tool_fetch_market_data
    params:
      asset_type: index
      view: historical
      asset_code: "000001"
      period: daily
      start_date: "20260201"
      end_date: "20260228"
```

Example: fetch ETF 5-minute bars:

```yaml
tools:
  - name: tool_fetch_market_data
    params:
      asset_type: etf
      view: minute
      asset_code: "510300"
      period: "5"
      start_date: "20260201"
      end_date: "20260228"
```

Example: fetch latest CPI and use macro snapshot:

```yaml
tools:
  - name: tool_fetch_macro_data
    params:
      dataset: cpi
      latest_only: true
  - name: tool_fetch_macro_snapshot
    params:
      scope: monthly
      include_quadrant: true
```

## Cache policy

- Default: `data_cache.enabled=false`
  - Disk parquet reads are allowed (if cache exists).
  - Disk parquet writes are skipped.
  - Corrupted parquet files are not deleted in this mode.
- `data_cache.enabled=true`
  - Disk parquet reads and writes are both enabled.

