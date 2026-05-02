# P3 分批迁移说明（Router + throttle 统一）

本迭代落实 **规划 P3** 的「可重复模式」文档化；**涨停工具链节拍**已在 `tool_fetch_limit_up_stocks` 的 AkShare approved 链（em → previous → strong → sub_new）落地，配置键：`data_sources.limit_up.upstream_chain_spacing_seconds`（助手 `market_data.yaml`，合并进进程配置；可覆盖 `OPENCLAW_LIMIT_UP_CHAIN_SPACING_SECONDS`）。**分钟链 / northbound** 等其余域仍可按同一模式在后续 PR 分批收紧。

## 统一模式

1. **优先级**：从 `config.yaml` / 助手 `market_data.yaml` 的 `data_sources.*.priority` 读取。
2. **节拍**：多源 `enumerate` 间使用助手 `data_collector._upstream_spacing_sleep`（附录 B）；采集任务链使用 `intraday_tool_spacing_seconds`。
3. **出口元数据**：HTTP/SDK 成功帧经 `with_source_meta`；闸门类与 `normalize_contract` 并存时在 **CONNECTORS** 矩阵声明。

## 试点代码锚点

- **全球指数**：`plugins/connectors/global_index/orchestrator.py` → `fetch_global.fetch_global_index_spot`（契约不变）。
- **Tushare 档位**：`plugins/connectors/tushare/__init__.py::get_permission_profile` 与助手 `market_data.yaml` 的 `tushare.permission_profile`。
