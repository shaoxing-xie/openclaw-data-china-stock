# Data Source Tool Inventory

This inventory is the baseline for source normalization and third-party configuration guidance.

- source of truth: `config/tools_manifest.yaml`
- current scope: 90 external `tool_*`
- normalization target: all tools should converge to canonical `source_id` semantics in outputs or wrappers.

## Canonical source_id (reference)

`akshare`, `tushare`, `mootdx`, `sina`, `eastmoney`, `ths`, `yfinance`, `fmp`, `tavily`, `baostock`, `efinance`, `cache`, `derived`, `fallback`, `unknown`

## Tool Matrix (all external tools)

| tool_id | domain | expected_source_ids |
|---|---|---|
| `tool_fetch_index_realtime` | index | `mootdx,sina,eastmoney,akshare,cache` |
| `tool_fetch_index_historical` | index | `tushare,akshare,sina,eastmoney,cache` |
| `tool_fetch_cni_index_daily` | index | `akshare` |
| `tool_fetch_csindex_index_daily` | index | `akshare` |
| `tool_fetch_index_minute` | index | `mootdx,sina,eastmoney,akshare,cache` |
| `tool_fetch_index_opening` | index | `akshare,sina,eastmoney,mootdx,cache` |
| `tool_fetch_index_data` | merged-index | `derived` |
| `tool_fetch_etf_data` | merged-etf | `derived` |
| `tool_fetch_option_data` | merged-option | `derived` |
| `tool_fetch_etf_realtime` | etf | `ths,sina,eastmoney,mootdx,akshare,cache` |
| `tool_fetch_etf_historical` | etf | `tushare,akshare,sina,eastmoney,cache` |
| `tool_fetch_etf_minute` | etf | `sina,eastmoney,mootdx,akshare,cache` |
| `tool_fetch_etf_iopv_snapshot` | etf | `sina,eastmoney,ths,derived` |
| `tool_fetch_option_realtime` | option | `sina,akshare,eastmoney,cache` |
| `tool_fetch_option_greeks` | option | `sina,akshare,eastmoney,cache` |
| `tool_fetch_option_minute` | option | `sina,akshare,eastmoney,cache` |
| `tool_fetch_a50_data` | futures | `sina,eastmoney,akshare,cache` |
| `tool_fetch_sector_data` | sector | `ths,sina,eastmoney,akshare,cache` |
| `tool_get_option_contracts` | utility | `sina,akshare` |
| `tool_check_trading_status` | utility | `derived` |
| `tool_get_a_share_market_regime` | utility | `derived` |
| `tool_filter_a_share_tradability` | utility | `derived` |
| `tool_read_market_data` | data-access | `cache,derived` |
| `tool_read_index_daily` | data-access | `cache,derived` |
| `tool_read_index_minute` | data-access | `cache,derived` |
| `tool_read_etf_daily` | data-access | `cache,derived` |
| `tool_read_etf_minute` | data-access | `cache,derived` |
| `tool_read_option_minute` | data-access | `cache,derived` |
| `tool_read_option_greeks` | data-access | `cache,derived` |
| `tool_fetch_stock_financials` | stock-fundamental | `eastmoney,akshare,tushare,cache` |
| `tool_fetch_a_share_universe` | stock-reference | `akshare,eastmoney,sina,ths,cache` |
| `tool_fetch_stock_financial_reports` | stock-reference | `akshare,eastmoney,sina,cache` |
| `tool_fetch_stock_corporate_actions` | stock-reference | `akshare,eastmoney,sina,cache` |
| `tool_fetch_margin_trading` | stock-reference | `akshare,eastmoney,tushare,cache` |
| `tool_fetch_block_trades` | stock-reference | `akshare,eastmoney,cache` |
| `tool_fetch_stock_shareholders` | stock-reference | `akshare,eastmoney,cache` |
| `tool_fetch_ipo_calendar` | stock-reference | `akshare,eastmoney,cache` |
| `tool_fetch_index_constituents` | stock-reference | `akshare,eastmoney,cache` |
| `tool_fetch_stock_research_news` | stock-reference | `akshare,eastmoney,sina,cache` |
| `tool_screen_equity_factors` | analysis | `derived,akshare,tushare,cache` |
| `tool_fetch_stock_historical` | stock | `tushare,akshare,sina,eastmoney,baostock,cache` |
| `tool_fetch_stock_minute` | stock | `mootdx,sina,eastmoney,akshare,efinance,cache` |
| `tool_fetch_stock_realtime` | stock | `mootdx,sina,eastmoney,akshare,tushare,cache` |
| `tool_stock_data_fetcher` | stock | `derived,mootdx,sina,eastmoney,akshare,tushare,cache` |
| `tool_stock_monitor` | stock | `derived,mootdx,sina,eastmoney,akshare,tushare,cache` |
| `tool_fetch_limit_up_stocks` | limit-up | `akshare,eastmoney,cache` |
| `tool_sector_heat_score` | limit-up | `derived` |
| `tool_write_limit_up_with_sector` | limit-up | `derived,cache` |
| `tool_limit_up_daily_flow` | limit-up | `derived,cache` |
| `tool_dragon_tiger_list` | short-term | `akshare,eastmoney,cache` |
| `tool_capital_flow` | short-term | `akshare,eastmoney,ths,tushare,cache` |
| `tool_fetch_northbound_flow` | flow | `tushare,eastmoney,cache` |
| `tool_fetch_a_share_fund_flow` | flow | `ths,eastmoney,akshare,tushare,cache` |
| `tool_fetch_a_share_technical_screener` | screener | `ths,akshare,cache` |
| `tool_fetch_policy_news` | morning-brief | `tavily,cache` |
| `tool_fetch_macro_commodities` | morning-brief | `yfinance,tavily,cache` |
| `tool_fetch_overnight_futures_digest` | morning-brief | `tavily,cache` |
| `tool_conditional_overnight_futures_digest` | morning-brief | `derived,tavily,cache` |
| `tool_fetch_announcement_digest` | morning-brief | `tavily,cache` |
| `tool_fetch_macro_data` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_snapshot` | macro | `akshare,tushare,cache,derived` |
| `tool_fetch_macro_pmi` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_cx_pmi` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_cx_services_pmi` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_enterprise_boom` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_lpi` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_cpi` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_ppi` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_m2` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_social_financing` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_new_credit` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_lpr` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_fx_reserves` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_gdp` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_industrial_value` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_fixed_asset` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_leverage` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_exports_imports` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_trade_balance` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_exports_yoy` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_unemployment` | macro | `akshare,tushare,cache` |
| `tool_fetch_macro_tax_receipts` | macro | `akshare,tushare,cache` |
| `tool_fetch_market_data` | merged-market | `derived` |
| `tool_calculate_technical_indicators` | analysis | `derived` |
| `tool_fetch_sector_constituents` | analysis | `akshare,ths,eastmoney,cache` |
| `tool_calculate_sector_breadth` | analysis | `derived` |
| `tool_calculate_sector_leadership` | analysis | `derived` |
| `tool_fetch_etf_share` | analysis | `akshare,eastmoney,cache` |
| `tool_calculate_share_trend` | analysis | `derived` |
| `tool_calculate_sector_momentum_v2` | analysis | `derived` |

## Required Governance

- New data source branch in any tool: update this file and `DATA_SOURCE_REGISTRY.md`.
- New external tool in `config/tools_manifest.yaml`: add a row in this file.
- If one tool maps to unknown source chain, use `unknown` and keep `source_raw`.
