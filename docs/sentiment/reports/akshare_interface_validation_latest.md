# AKShare Interface Validation Report

- generated_at: 2026-04-18 16:43:39

## Signatures

- `stock_zt_pool_em`: `(date: str = '20241008') -> pandas.DataFrame`
- `stock_market_fund_flow`: `() -> pandas.DataFrame`
- `stock_sector_fund_flow_rank`: `(indicator: str = '今日', sector_type: str = '行业资金流') -> pandas.DataFrame`
- `stock_individual_fund_flow_rank`: `(indicator: str = '5日') -> pandas.DataFrame`
- `stock_hsgt_fund_flow_summary_em`: `() -> pandas.DataFrame`
- `stock_sector_spot`: `(indicator: str = '新浪行业') -> pandas.DataFrame`
- `stock_board_industry_name_em`: `() -> pandas.DataFrame`

## Cases

| interface | ok | elapsed_ms | record_count | columns_sample | error |
|---|---:|---:|---:|---|---|
| stock_zt_pool_em | 0 | 10096 | 0 |  | ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer')) |
| stock_market_fund_flow | 0 | 10116 | 0 |  | ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer')) |
| stock_sector_fund_flow_rank | 0 | 10140 | 0 |  | ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer')) |
| stock_individual_fund_flow_rank | 0 | 10098 | 0 |  | ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer')) |
| stock_hsgt_fund_flow_summary_em | 0 | 10053 | 0 |  | ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer')) |
| stock_sector_spot_行业 | 0 | 10009 | 0 |  | Expecting value: line 1 column 1 (char 0) |
| stock_board_industry_name_em | 0 | 35017 | 0 |  | ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer')) |
