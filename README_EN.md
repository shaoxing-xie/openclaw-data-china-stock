# openclaw-data-china-stock

OpenClaw/ClawHub plugin for collecting A-share, ETF, and listed option market data.

## What you get

This plugin reuses the upstream `data_collection` and `merged` tool implementations and exposes stable `tool_*` interfaces for:

- Index / ETF / Option market data (realtime, historical, minute, opening/greeks).
- Option contracts (by underlying).
- Optional: pre-market/policy/news, sector rotation, limit-up pool, northbound flow, and more.
- Optional: local Parquet cache reads.

## Recommended usage

1. Configure the tool runner path in OpenClaw plugin settings to point to:
   - `tool_runner.py` in this repository.
2. In your Agent/Workflow, call:
   - `tool_fetch_market_data` as the primary cross-asset unified entry.
3. For cached/offline scenarios (when enabled), use:
   - `tool_read_market_data` or `tool_read_index_*` / `tool_read_etf_*` / `tool_read_option_*`.

## MVP tools (recommended)

- `tool_fetch_market_data`
  - Cross-asset unified entry (recommended).
- `tool_get_option_contracts`
  - Get option contracts for a given underlying.
- Compatibility unified entries:
  - `tool_fetch_index_data`
  - `tool_fetch_etf_data`
  - `tool_fetch_option_data`

## Cache policy (important)

### Disk cache semantics

This plugin is designed so that **disk parquet writes are disabled by default**.

In `config.yaml`:

- `data_cache.enabled: false` (default)
  - Disk cache reads are allowed (if existing parquet exists).
  - Disk cache writes are skipped (the plugin will not create/overwrite parquet files).
  - If a cached parquet is unreadable/corrupted, the plugin avoids deleting it in this mode.
- `data_cache.enabled: true`
  - Disk cache reads and writes are both enabled.

### Common tool return contract (recommended fields)

Most `tool_*` functions return a JSON object that typically includes:

- `success`: `true|false`
- `data`: fetched/processed payload (may be `null` on failure)
- `message`: human-readable status/error message
- `source`: where the data came from (e.g., provider name or `cache`)

Some tools additionally provide (when available):

- `count`: number of records/contracts
- `missing_dates`: dates that were not found in cache (used by cache-read tools)
- `timestamp`: data timestamp / query time (string)
- `cache_hit`: whether cache was used (`true|false`)
- `cache_hit_detail`: extra cache hit diagnostics (e.g., which dates/partitions were hit)

### Provider fallback and retries (from `config.yaml`)

The plugin follows the provider priority order in `data_sources.*.priority` (for example, `sina -> eastmoney`), and retries according to:

- Circuit breaker (`data_sources.circuit_breaker`)
  - `enabled`: whether it is enabled
  - `error_threshold`: consecutive error threshold (default `3`)
  - `cooldown_seconds`: cooldown after tripping (default `300`)
- Per-provider retry settings (e.g., `data_sources.etf_minute.eastmoney/sina`)
  - `enabled`: whether the provider is enabled
  - `max_retries`: maximum retry count
  - `retry_delay`: delay between retries (seconds)

