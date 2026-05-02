# Data Source Registry

This document defines the canonical `source_id` standard for all `tool_*` outputs in `openclaw-data-china-stock`.

## Canonical source_id

- `akshare`
- `tushare`
- `mootdx`
- `sina`
- `eastmoney`
- `ths`
- `yfinance`
- `fmp`
- `tavily`
- `baostock`
- `efinance`
- `cache`
- `derived`
- `fallback`
- `unknown`

## Alias Mapping Rules

- `eastmoney*`, `*_em`, `eastmoney_http*` -> `eastmoney`
- `sina*`, `*sinajs*`, `*_sina` -> `sina`
- `ths*`, `*tonghuashun*`, `*_ths` -> `ths`
- `akshare*` -> `akshare`
- `tushare*` -> `tushare`
- `financialmodelingprep*`, `fmp*` -> `fmp`
- `yfinance` -> `yfinance`
- `mootdx*` -> `mootdx`
- `cache*` -> `cache`
- `fallback|none` -> `fallback`
- unmatched -> `unknown`

## Unified Source Fields (tool output)

All externally exposed tools SHOULD gradually converge to the following fields:

- `source_id`
- `source`
- `source_raw`
- `source_stage` (`primary|fallback|cache|derived`)
- `source_vendor` (optional)
- `source_interface` (optional)

## Tool Inventory Scope

Canonical inventory scope for normalization is `config/tools_manifest.yaml` (`tools[*].id`), currently 88 tools.

**Connectors cross-table**: see [`DATA_SOURCE_CONNECTORS.md`](./DATA_SOURCE_CONNECTORS.md) for business-mapping rows and the **metadata dual-track matrix** (P0-surface / P1).

### Domain-based tool/source map

- **Index / global index / ETF / option**
  - likely `akshare|sina|eastmoney|mootdx|yfinance|fmp|cache`
  - `tool_fetch_cni_index_daily` -> `akshare` (`index_hist_cni`)
  - `tool_fetch_csindex_index_daily` -> `akshare` (`stock_zh_index_hist_csindex`)
- **A-share stock realtime/minute/historical**
  - likely `mootdx|sina|eastmoney|akshare|tushare|baostock|efinance|cache`
- **Fund flow / northbound / sector / limit-up**
  - likely `ths|eastmoney|akshare|tushare|cache`
- **Macro / morning brief / policy digest**
  - likely `tavily|yfinance|akshare|cache`
- **Risk / strategy / notification wrappers**
  - mostly `derived` (if no direct remote pull)

## Contribution Rule (Required)

- Any PR that adds a new data source branch MUST update this file.
- Any PR that adds a new external `source_id` MUST:
  - add it to canonical list
  - add alias mapping
  - document proxy strategy and fallback order
- If a new tool is added to `config/tools_manifest.yaml`, update domain-based mapping section.

## Third-party Configuration Guidance

For each data source configured in `config.yaml` / assistant domain config, third-party users should be able to locate:

- source id
- auth env keys
- proxy policy key path (`network.proxy.per_source.<source_id>`)
- fallback order
