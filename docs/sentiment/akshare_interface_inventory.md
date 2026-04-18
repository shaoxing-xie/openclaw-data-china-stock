# AKShare Interface Inventory (Sentiment Tools)

This inventory is the P0-0 baseline for four tools:
- `tool_fetch_limit_up_stocks`
- `tool_fetch_a_share_fund_flow`
- `tool_fetch_northbound_flow`
- `tool_fetch_sector_data`

## Core interfaces (first-wave 6)

| data_object | ak_function | required_params | optional_params | key_fields | market_session_behavior | known_fail_modes |
|---|---|---|---|---|---|---|
| `limit_up_pool` | `stock_zt_pool_em` | `date` | - | 代码, 名称, 涨跌幅, 连板数, 首封时间 | 交易日盘中/盘后可返回，非交易日可能空 | 空表、字段漂移 |
| `market_fund_flow` | `stock_market_fund_flow` | - | - | 日期, 主力净流入 | 盘中刷新，盘后稳定 | 偶发断连 |
| `sector_fund_rank` | `stock_sector_fund_flow_rank` | `indicator`, `sector_type` | - | 名称, 净流入, 涨跌幅 | 盘中可用，窗口受限（今日/5日/10日） | RemoteDisconnected、空表 |
| `stock_fund_rank` | `stock_individual_fund_flow_rank` | `indicator` | - | 代码, 名称, 主力净流入 | 盘中可用，分页接口较慢 | 超时、空表 |
| `northbound_summary` | `stock_hsgt_fund_flow_summary_em` | - | - | 交易日, 板块, 资金方向, 成交净买额 | 日终汇总语义更可靠 | 字段变化、空结果 |
| `sector_snapshot` | `stock_sector_spot` | `indicator` | - | 板块, 涨跌幅 | 截面快照 | 空表、字段不全 |

## Extended interfaces (P1 completion)

| data_object | ak_function | usage |
|---|---|---|
| `industry_board_snapshot` | `stock_board_industry_name_em` | `tool_fetch_sector_data` 备用源 |
| `sector_flow_summary` | `stock_sector_fund_flow_summary` | `tool_fetch_a_share_fund_flow` 下钻 |
| `sector_flow_hist` | `stock_sector_fund_flow_hist` / `stock_concept_fund_flow_hist` | 历史趋势补充 |
| `stock_fund_history` | `stock_individual_fund_flow` | 个股资金历史 |
| `big_deal_flow` | `stock_fund_flow_big_deal` | 大单追踪末级兜底 |

## Notes

- Final primary/secondary order is not auto-approved; every downgrade chain is confirmed with user review.
- Validation evidence is recorded in `docs/sentiment/reports/akshare_interface_validation_latest.md`.
