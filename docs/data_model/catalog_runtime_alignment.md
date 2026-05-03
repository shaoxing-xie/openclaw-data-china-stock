# factor_registry（source_chains）与运行时对齐

## 真源与合并规则

- **YAML**：`config/factor_registry.yaml` 的 `source_chains` 为声明式顺序；与 `data_sources.*` 系统配置 **并存期**由代码做 **安全合并**，避免未在运行时实现的 tag 强行插队。
- **全球指数现货**（`global_index_spot`）：仅识别与 `fetch_global_index_spot` 循环一致的源 id：`yfinance`、`fmp`、`sina`。合并逻辑见 `plugins.utils.plugin_data_registry.merge_global_index_spot_priority`；结果写入响应 `source_route.active_priority` 与 `source_route.catalog_merge`。
- **A 股主力资金流**（`a_share_fund_flow`）：`_run_chain` 内 `(ths|eastmoney)` 元组在应用 `provider_preference` 之前，先按 catalog 的 `provider_tags` 重排；`cache` 等占位 tag 被忽略。
- **技术指标引擎**（`technical_indicators`）：`engine_preference=auto`（及历史遗留未知取值）时，`TechnicalIndicatorEngine.select` 按 `provider_tags` 顺序在 **已实现** 的 `talib` / `pandas_ta` / `builtin` 中选第一个可用项；`tool_calculate_technical_indicators` 的 `meta.catalog_engine_order` 反映解析后的顺序。

## 配置优先与回滚

- **优先**：系统 `data_sources.global_index.latest.priority` 仍决定 **可用源集合**；catalog 只在该集合内重排相对顺序。
- **回滚**：将 `source_chains.global_index_spot.provider_tags` 留空或删除该键 → 退化为 `merge_mode=config_only_empty_catalog`，行为与仅读系统配置一致。
- **紧急**：环境或部署层可继续用既有 `data_sources` 覆盖；无需改代码。

## 退出条件（停止双轨）

- 当所有已 catalog 化路径的 **合并后顺序** 与 YAML 一致且连续 **两个发版周期**无回滚需求时，可在发版说明中宣布「系统 priority 仅作白名单/开关，顺序以 catalog 为准」，并逐步收紧系统配置中的顺序字段（仍保留 fmp 开关、密钥等）。

## 观测

- `tool_plugin_catalog_digest`：只读 registry + manifest 规模摘要。
- `tool_summarize_attempts(..., dataset_id=...)`：为 attempts 聚合打上 dataset 维度标签。
- `tool_probe_source_health(..., include_catalog_digest=True)`：在探针结果旁附带 catalog 摘要（无网络）。
