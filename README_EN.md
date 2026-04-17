# openclaw-data-china-stock

**A market-data foundation for A-share retail workflows on OpenClaw / ClawHub**

An open-source, free **OpenClaw code plugin** that exposes a unified set of `tool_*` endpoints for Chinese indices, ETFs, stocks, and listed options—with multi-provider priority/fallback and a safe-by-default disk cache policy (`data_cache.enabled=false`: read existing Parquet if present; **no parquet writes** by default).

**In one sentence**: spend less time fighting unstable endpoints, inconsistent formats, and cache surprises—and more time on strategy and engineering.

---

### Highlights

- **Unified entry**: Prefer `tool_fetch_market_data` across index / ETF / stock / option assets; stocks also support `timeshare`, `pre_market`, `market_overview`, and `valuation_snapshot` views.
- **Multi-source resilience**: AkShare, Sina, Eastmoney, optional Tushare, plus circuit breaker / retries as configured—reducing single-point outages in Agent workflows.
- **Cache you control**: Parquet **writes** are off by default; enable `data_cache.enabled=true` in `config.yaml` only when you want local read/write caching.
- **Retail-oriented tools**: limit-up lists, dragon-tiger, northbound flow, **onshore A-share fund flow** (`tool_fetch_a_share_fund_flow`), **technical stock screeners** (`tool_fetch_a_share_technical_screener`), sector heat, option Greeks, trading-status helpers, and more (as registered in `config/tools_manifest.json`).
- **China macro (v0.4.0)**: `tool_fetch_macro_data` / `tool_fetch_macro_snapshot` plus 21 compatibility wrappers and the `china-macro-analyst` skill.
- **Predictable JSON**: Most tools return objects with `success`, `data`, `message`, `source` (and optional cache metadata). A-share extended tools usually add `provider`, `fallback_route`, and `attempt_counts` for observability.

---

### A-share extended tool system (P0 / P1 and unified entry)

This section summarizes **new or strengthened** A-share capabilities (see `config/tools_manifest.json`). Design: **one tool per domain, parameters for sub-modes**—not one OpenClaw tool per raw AkShare endpoint. Optional **`provider_preference`** reorders multi-source attempts alongside the internal fallback chain.

#### Layers and tools

| Layer | Tool ID | Role | Key parameters (excerpt) |
|-------|---------|------|--------------------------|
| **P0** | `tool_fetch_a_share_universe` | CSI A-share code/name master list | `max_rows`; `provider_preference`: `auto` / `standard` / `eastmoney` |
| **P0** | `tool_fetch_stock_financial_reports` | Balance / income / cashflow statements by report period | `statement_type`: `balance` / `income` / `cashflow`; `provider_preference`: `auto` / `eastmoney` / `sina` |
| **P0** | `tool_fetch_stock_corporate_actions` | Dividends, unlocks, issuance, allotment, buyback | `action_kind`: `dividend` / `restricted_unlock` / `issuance` / `allotment` / `buyback`; some modes need `stock_code` or dates |
| **P0** | `tool_fetch_margin_trading` | Margin trading (SSE/SZSE summary, detail, SZSE underlying list) | `market`: `sh` / `sz`; `data_kind`: `summary` / `detail` / `underlying_sz`; `date` / `start_date` / `end_date` by kind |
| **P0** | `tool_fetch_block_trades` | Block trades (stats, A-share daily lines, active names, broker rankings) | `block_kind`: `sctj` / `mrtj` / `mrmx` / `hygtj` / `yybph`; `start_date` / `end_date` / `window` |
| **P1** | `tool_fetch_stock_shareholders` | Top holders, float holders, holder count, fund holders | `holder_kind`: `top10` / `top10_float` / `holder_count` / `holder_change_ths` / `fund_holder`; holder-count mode: `provider_preference`: `cninfo` / `ths` |
| **P1** | `tool_fetch_ipo_calendar` | IPO pipeline: filings, new listings, review board, tutoring, per-stock IPO summary | `ipo_kind`: `declare_em` / `new_list_cninfo` / `review_em` / `tutor_em` / `stock_detail` / `stock_summary`; last two need `stock_code` |
| **P1** | `tool_fetch_index_constituents` | Index members; optional CSI weight | `index_code`; `include_weight`; `provider_preference`: `auto` / `csindex` / `sina` / `eastmoney` |
| **P1** | `tool_fetch_stock_research_news` | Stock news, research reports, main CX feed | `content_kind`: `news` / `research` / `main_feed`; `main_feed` does not require a symbol; `max_rows` |

Complements existing **`tool_fetch_stock_financials`** (valuation snapshot) vs **`tool_fetch_stock_financial_reports`** (report-period statements).

#### Stock-only `view` values on `tool_fetch_market_data`

When **`asset_type=stock`**, besides `realtime` / `historical` / `minute` / `opening`:

| `view` | Meaning | Typical args |
|--------|---------|--------------|
| `timeshare` | Intraday timeseries for the current session | `asset_code` |
| `pre_market` | Pre-market reference / minute | `asset_code`; `start_date` / `end_date` (YYYYMMDD) |
| `market_overview` | Light aggregate market snapshot | `start_date` optional; `asset_code` optional |
| `valuation_snapshot` | Quick valuation / key metrics | `asset_code` |

**Implementation / manifests**: `plugins/data_collection/stock/fundamentals_extended.py`, `stock/reference_p1.py`, `stock/unified_stock_views.py`, `utils/provider_preference.py`; parameters in `config/tools_manifest.yaml` / `.json`. Capability cards: [plugins/data_collection/ROADMAP.md](plugins/data_collection/ROADMAP.md) appendices F–G.

---

### Installation

**Published version (check registry): `0.4.0`** (see [CHANGELOG.md](CHANGELOG.md).)

**From ClawHub / registry (recommended)**

If one command fails, try the other (depends on OpenClaw version and CLI):

```bash
openclaw plugins install clawhub:@shaoxing-xie/openclaw-data-china-stock
```

```bash
openclaw plugins install @shaoxing-xie/openclaw-data-china-stock
```

After installing or upgrading, **restart the OpenClaw Gateway** (or equivalent) and confirm the plugin/tools load in the Dashboard or via `openclaw status`.

**From GitHub (local debugging / contributing)**

```bash
git clone https://github.com/shaoxing-xie/openclaw-data-china-stock.git
cd openclaw-data-china-stock
pip install -r requirements.txt
```

How you mount this folder as an extension depends on your OpenClaw setup (e.g., copy/link into `extensions` and allowlist in `openclaw.json`). Run `openclaw plugins install --help` to see whether **path-based** or **linked** installs are supported on your machine.

### Testing

- **Unit tests (no network)**: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- **Full-tool smoke (optional, may hit the network)**: `python3 scripts/test_all_tools.py --manifest config/tools_manifest.json --report tool_test_report.json` (use `--limit` / `--disable-network` as needed). By default, `tool_fetch_market_data` is also run several extra times for stock-only views (`timeshare`, `pre_market`, `market_overview`, `valuation_snapshot`); those runs use `max(--timeout-seconds, --extra-stock-market-view-min-timeout)` (default min **120s**) so intraday/timeshare is not killed at 45s. Pass `--no-extra-stock-market-views` to skip for speed. A single subprocess timeout is recorded as a failed row and does **not** abort the script.
- **L4 column-contract tests (mock, no network)**: `tests/test_dto_snapshots_l4.py` and `tests/fixtures/l4/*.json` lock `data[0]` keys for selected tools; update fixtures when upstream columns change.
- **Report diff (release gate)**: `python3 scripts/compare_tool_reports.py <baseline.json> <current.json>` exits `1` if failures increase; set `COMPARE_STRICT=0` to print only. Optional baseline file and CI step: see `.github/workflows/unittest.yml`.
- Capability cards: [plugins/data_collection/ROADMAP.md](plugins/data_collection/ROADMAP.md) appendices F–G.

### OpenClaw dev registration (recommended)

If you develop in this repository and want OpenClaw to discover the new macro tools and the `china-macro-analyst` skill immediately:

```bash
.venv/bin/python scripts/register_openclaw_dev.py
```

This updates `~/.openclaw/openclaw.json` in an append-only way and exposes the skill into the OpenClaw workspace.

---

### Three-minute quick start

1. In plugin settings, ensure `scriptPath` points at the packaged `tool_runner.py` (defaults are usually fine).
2. In Agents/Workflows, call **`tool_fetch_market_data` first**.
3. For offline / weak-network flows, pair with `tool_read_market_data` and other `tool_read_*` tools (requires existing cache files).

**Index daily historical example**

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

**CSI 300 ETF 5-minute bars**

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

**Option Greeks**

```yaml
tools:
  - name: tool_fetch_market_data
    params:
      asset_type: option
      view: greeks
      contract_code: "10010910"
```

**Stock intraday timeshare (`view` on unified entry):**

```yaml
tools:
  - name: tool_fetch_market_data
    params:
      asset_type: stock
      view: timeshare
      asset_code: "600000"
      mode: production
```

**More examples**: `tool_fetch_a_share_universe`, `tool_fetch_index_constituents`, `tool_fetch_limit_up_stocks`, `tool_fetch_northbound_flow`, `tool_fetch_a_share_fund_flow`, `tool_fetch_a_share_technical_screener`, `tool_dragon_tiger_list`—see **A-share extended tool system** above and the full list below.

### Tushare fallback

Some routes may use Tushare as an optional fallback: set `TUSHARE_TOKEN` or `tushare.token` in `config.yaml`.

---

### Default cache semantics

With `data_cache.enabled=false` (default), the plugin may **read** existing on-disk Parquet caches but **skips writing** new/updated Parquet files (reducing accidental data pollution). Details below under **Cache policy (important)**.

---

## What you get

- Index / ETF / **Stock** / Option market data (realtime, historical, minute, opening, Greeks).
- **A-share foundation extensions**: master list, three financial statements, corporate actions, margin & block trades; P1 shareholders / IPO / index constituents / news & research; stock `view` extras on `tool_fetch_market_data` (`timeshare`, `pre_market`, `market_overview`, `valuation_snapshot`) as listed in the manifest.
- Option contracts (by underlying).
- Optional capabilities: pre-market/policy/news, sector rotation, limit-up pool, northbound flow, etc.
- Optional local Parquet cache reads.

---

## Why this exists / who it is for

Many retail workflows don’t lack random data—they lack a **stable, reasonably uniform** layer: inconsistent provider schemas, flaky single endpoints, and hard-to-audit caches. This plugin standardizes parameters and return shapes and adds provider priority + fallback so “fetch market data” is a maintainable set of `tool_*` calls.

- Retail investors focused on A-shares / ETFs / listed options  
- Users who want repeatable OpenClaw/Agent workflows without bespoke scrapers per provider  
- Developers who want consistent tool contracts without re-solving China market plumbing every time  

---

## Disclaimer

This plugin is for **data collection and technical research only**. It is not investment advice and does not guarantee any outcome. You are responsible for your use and any risks.

---

## Recommended usage

1. Confirm `tool_runner.py` resolves correctly in plugin settings.  
2. Prefer `tool_fetch_market_data` in Agents/Workflows.  
3. For cache-backed reads, use `tool_read_market_data` / `tool_read_*`; enable `data_cache.enabled=true` only when you explicitly want local Parquet writes and understand paths/disk usage.  

---

## Background

`openclaw-data-china-stock` targets A-share market data collection—indices, ETFs, stocks, and listed options—via unified `tool_*` endpoints for OpenClaw. Disk cache **writes** are off by default (`data_cache.enabled` in `config.yaml`), suited to “online fetch first + read cache if present”.

---

## Pain points → approach

- **Broad coverage**: realtime/historical/minute data and contract lookup across major asset types.  
- **More stable fetches**: provider priority + automatic fallback.  
- **Controlled caching**: no disk writes by default; opt-in when needed.  
- **One primary entry**: `tool_fetch_market_data`, plus compatibility entries `tool_fetch_index_data`, `tool_fetch_etf_data`, `tool_fetch_option_data`.  

---

## Data-domain overview (aligned with ROADMAP)

| Domain | Example tools | Notes |
|--------|---------------|-------|
| Quote | `tool_fetch_market_data`, `tool_fetch_stock_*` | Stock extras: `timeshare`, `pre_market`, `market_overview`, `valuation_snapshot` |
| Fundamentals | `tool_fetch_stock_financials`, `tool_fetch_stock_financial_reports` | Snapshot vs report-period statements; optional `provider_preference` |
| Reference | `tool_fetch_a_share_universe`, `tool_fetch_index_constituents`, `tool_get_option_contracts` | Universe, index constituents, contracts, sessions |
| Shareholders / IPO / news (P1) | `tool_fetch_stock_shareholders`, `tool_fetch_ipo_calendar`, `tool_fetch_stock_research_news` | Holders, IPO tables, news & research |
| Corporate | `tool_fetch_stock_corporate_actions` | Dividends, unlocks, issuance, buybacks |
| Market microstructure | `tool_fetch_margin_trading`, `tool_fetch_block_trades`, `tool_dragon_tiger_list` | Margin, block trades, dragon-tiger |
| Flow & sentiment | `tool_fetch_northbound_flow`, `tool_capital_flow`, `tool_fetch_a_share_fund_flow`, `tool_fetch_a_share_technical_screener`, limit-up/sector tools | |
| Session | `tool_fetch_policy_news`, digest tools | Tavily / search-style |

---

## MVP tool categories & interface list (release exposure)

Notes:
- “Available” means the tool is registered in `config/tools_manifest.yaml` (runtime uses `config/tools_manifest.json`).
- “Not in the current MVP tool subset” means the implementation exists but is not exposed in the current published tool subset.

### Cross-asset unified entry (recommended)

- `tool_fetch_market_data` (Available)
  - `asset_type=index|etf|option|stock`; `view` includes `realtime|historical|minute|opening|greeks|global_spot|iopv_snapshot` plus stock-only `timeshare|pre_market|market_overview|valuation_snapshot`

### Compatibility entries (merged three entries)

- `tool_fetch_index_data` (Available)
- `tool_fetch_etf_data` (Available)
- `tool_fetch_option_data` (Available)

### Index (Index)

- `tool_fetch_index_realtime` (Available)
- `tool_fetch_index_historical` (Available)
- `tool_fetch_index_minute` (Available)
- `tool_fetch_index_opening` (Available)
- `tool_fetch_global_index_spot` (Not in the current MVP tool subset)

### ETF (ETF)

- `tool_fetch_etf_realtime` (Available)
- `tool_fetch_etf_historical` (Available)
- `tool_fetch_etf_minute` (Available)
- `tool_fetch_etf_iopv_snapshot` (Available)

### Options (Option)

- `tool_fetch_option_realtime` (Available)
- `tool_fetch_option_greeks` (Available)
- `tool_fetch_option_minute` (Available)

### Futures (Futures)

- `tool_fetch_a50_data` (Available)

### Stocks & aggregation (Stock)

- `tool_fetch_stock_realtime` (Available)
- `tool_fetch_stock_historical` (Available)
- `tool_fetch_stock_minute` (Available)
- `tool_stock_data_fetcher` (Available)
- `tool_stock_monitor` (Available)

### Financials (Financials)

- `tool_fetch_stock_financials` (Available)
- `tool_fetch_stock_financial_reports` (Available)

### A-share universe / corporate / margin / block trades

- `tool_fetch_a_share_universe` (Available)
- `tool_fetch_stock_corporate_actions` (Available)
- `tool_fetch_margin_trading` (Available)
- `tool_fetch_block_trades` (Available)

### Shareholders / IPO / index constituents / news & research (P1)

- `tool_fetch_stock_shareholders` (Available)
- `tool_fetch_ipo_calendar` (Available)
- `tool_fetch_index_constituents` (Available)
- `tool_fetch_stock_research_news` (Available)

Optional **`provider_preference`** (`auto`, `eastmoney`, `sina`, `csindex`, `cninfo`, `ths`, `standard`, …) reorders multi-source attempts alongside the internal fallback chain.

### Limit-up / sector heat / dragon-tiger / capital flow / northbound

- `tool_fetch_limit_up_stocks` (Available)
- `tool_sector_heat_score` (Available)
- `tool_write_limit_up_with_sector` (Available)
- `tool_limit_up_daily_flow` (Available)
- `tool_dragon_tiger_list` (Available)
- `tool_capital_flow` (Available; per-stock flow summary)
- `tool_fetch_a_share_fund_flow` (Available; onshore money-flow tables via `query_kind`, multi-source)
- `tool_fetch_a_share_technical_screener` (Available; Tonghuashun `stock_rank_*_ths` screeners)
- `tool_fetch_northbound_flow` (Available)
- `tool_fetch_sector_data` (Available)

### Pre-market / policy / macro / announcements / industry news

- `tool_fetch_policy_news` (Available)
- `tool_fetch_macro_commodities` (Available)
- `tool_fetch_overnight_futures_digest` (Available)
- `tool_conditional_overnight_futures_digest` (Available)
- `tool_fetch_announcement_digest` (Available)
- `tool_fetch_industry_news_brief` (Not in the current MVP tool subset)

### Trading sessions / contracts / tradability (Utils)

- `tool_get_option_contracts` (Available)
- `tool_check_trading_status` (Available)
- `tool_get_a_share_market_regime` (Available)
- `tool_filter_a_share_tradability` (Available)
- `tool_fetch_multiple_etf_realtime` (Not in the current MVP tool subset)
- `tool_fetch_multiple_index_realtime` (Not in the current MVP tool subset)
- `tool_fetch_multiple_option_realtime` (Not in the current MVP tool subset)
- `tool_fetch_multiple_option_greeks` (Not in the current MVP tool subset)

### Local cache reads (read_*)

- `tool_read_market_data` (Available)
- `tool_read_index_daily` (Available)
- `tool_read_index_minute` (Available)
- `tool_read_etf_daily` (Available)
- `tool_read_etf_minute` (Available)
- `tool_read_option_minute` (Available)
- `tool_read_option_greeks` (Available)

### Tick (optional, not in MVP)

- `fetch_tick_with_quality` (Not exposed as tool_*)

---

### MVP tools (try these first)

- `tool_fetch_market_data` — primary cross-asset entry; for stocks, use extra `view` values (`timeshare`, `pre_market`, `market_overview`, `valuation_snapshot`) when needed  
- `tool_get_option_contracts` — list contracts by underlying  
- **A-share base**: P0 tools for universe, financial statements, corporate actions, margin, block trades; P1 for shareholders, IPO, index constituents, news/research (see **A-share extended tool system** above)  
- Compatibility: `tool_fetch_index_data`, `tool_fetch_etf_data`, `tool_fetch_option_data`  

---

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

## Common tool return contract (recommended fields)

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

A-share extended tools (P0/P1 and some stock views on `tool_fetch_market_data`) may also return:

- `provider` / `fallback_route`: effective data source or ordered route list
- `attempt_counts`: attempt counts per upstream route (object), useful for support / debugging

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

---

## More resources

- Source & issues: [GitHub — shaoxing-xie/openclaw-data-china-stock](https://github.com/shaoxing-xie/openclaw-data-china-stock)
- ClawHub listing: [Plugin page on ClawHub](https://clawhub.ai/plugins/%40shaoxing-xie%2Fopenclaw-data-china-stock)

---

## License

MIT License (open-source and free-to-use).
