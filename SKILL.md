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

## Safety and independence

The plugin is designed to run independently (no dependency on any other repository):

- It does not inject `~/.openclaw/.env`.
- It supports plugin-specific cache/data paths (configured inside the plugin).

## Cache policy

- Default: `data_cache.enabled=false`
  - Disk parquet reads are allowed (if cache exists).
  - Disk parquet writes are skipped.
  - Corrupted parquet files are not deleted in this mode.
- `data_cache.enabled=true`
  - Disk parquet reads and writes are both enabled.

