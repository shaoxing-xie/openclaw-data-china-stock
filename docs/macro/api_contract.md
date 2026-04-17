# Macro API Contract

## Unified entry

### `tool_fetch_macro_data`

Request:

- `dataset` (required)
- `latest_only` (optional, default `false`)
- `lookback` (optional, default `24`)
- `frequency` (optional, default `monthly`)

Response fields:

- `success`: boolean
- `data`: object or null
- `source`: string
- `as_of`: string or null
- `unit`: string
- `data_lag_days`: number or null
- `staleness_days`: number or null
- `warnings`: string[]
- `error`: object or null

### `tool_fetch_macro_snapshot`

Request:

- `scope` (optional)
- `include_quadrant` (optional)

Response:

- `success`
- `data.growth`
- `data.inflation`
- `data.credit`
- `data.quadrant` (optional placeholder; skill config should decide final mapping)

## Compatibility tools

`tool_fetch_macro_*` wrappers remain available for backward compatibility.

## Tool Scope Boundary (Important)

To reduce third-party integration ambiguity, macro-prefixed tools are split into:

- **Primary (recommended)**:
  - `tool_fetch_macro_data`
  - `tool_fetch_macro_snapshot`
- **China Macro Analyst compatibility wrappers (exactly 21)**:
  - `tool_fetch_macro_pmi`
  - `tool_fetch_macro_cx_pmi`
  - `tool_fetch_macro_cx_services_pmi`
  - `tool_fetch_macro_enterprise_boom`
  - `tool_fetch_macro_lpi`
  - `tool_fetch_macro_cpi`
  - `tool_fetch_macro_ppi`
  - `tool_fetch_macro_m2`
  - `tool_fetch_macro_social_financing`
  - `tool_fetch_macro_new_credit`
  - `tool_fetch_macro_lpr`
  - `tool_fetch_macro_fx_reserves`
  - `tool_fetch_macro_gdp`
  - `tool_fetch_macro_industrial_value`
  - `tool_fetch_macro_fixed_asset`
  - `tool_fetch_macro_leverage`
  - `tool_fetch_macro_exports_imports`
  - `tool_fetch_macro_trade_balance`
  - `tool_fetch_macro_exports_yoy`
  - `tool_fetch_macro_unemployment`
  - `tool_fetch_macro_tax_receipts`
- **Adjacent legacy macro-prefixed tools (outside analyst scope)**:
  - `tool_fetch_macro_commodities`

Third-party users should default to **Primary** tools and treat wrappers as compatibility only.

