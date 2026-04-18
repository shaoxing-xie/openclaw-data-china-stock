# market-scanner

## 与 `market-sentinel` 如何选

| 场景 | 使用 |
|------|------|
| 盘前/盘中/盘后扫描、异动清单、板块热点与事件窗 | `market-scanner`（本 Skill） |
| 四工具情绪聚合综合分、阶段标签、主导因子与反证（非扫描清单） | `market-sentinel`（见 `skills/market-sentinel/README.md`） |

## 能力说明

- 盘前、盘中、盘后三模式扫描。
- 聚合指数、板块、资金流、涨停池形成统一市场快照。
- 输出情绪阶段判断与操作剧本（非交易指令）。

## 触发示例

- 现在市场什么状态
- 给我一份盘前扫描
- 做一个今天盘后复盘

## 依赖工具

- `tool_check_trading_status`
- `tool_fetch_market_data`
- `tool_fetch_sector_data`
- `tool_fetch_a_share_fund_flow`
- `tool_fetch_northbound_flow`
- `tool_fetch_limit_up_stocks`

