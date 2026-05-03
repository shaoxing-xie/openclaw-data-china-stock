# 助手仓协同检查清单（Phase 5 / Step09）

在 **etf-options-ai-assistant**（或等价宿主）侧执行：

1. **去重**：`rg tool_l4_valuation_context|tool_l4_pe_ttm_percentile|tool_plugin_catalog_digest|tool_resolve_symbol|tool_screen_equity_factors|tool_screen_by_factors` 确认无重复自算逻辑。
2. **契约**：若宿主使用 `data/meta/schema_registry.yaml` / `task_data_map.yaml`，为新增插件 schema（如 `valuation_context_v1`、`pe_ttm_percentile_band_v1`、`rotation_feature_aggregate_v1`）补充条目与 `data_layer` 映射；插件侧 JSON Schema 见 `openclaw-data-china-stock/docs/schemas/`。
3. **发版**：在开发仓发布插件后更新 `~/.openclaw/extensions/openclaw-data-china-stock`（或 OpenClaw 指定安装路径），校验 `openclaw.plugin.json` 版本号。
4. **验收**：对宿主 `curl` 语义层只读 API（若存在）做一次 smoke；否则以宿主 README 为准。

宿主工作区 **`etf-options-ai-assistant/data/meta/`** 已放置 **`schema_registry.yaml`**、**`task_data_map.yaml`**、**`data_contract_version.json`** 作为契约起步集；新增插件 schema 时请同步增量更新上述文件并列出发版说明。

继续遵守：不直接修改运行时 **`~/.openclaw/extensions/openclaw-data-china-stock`**；插件迭代在 **openclaw-data-china-stock** 开发仓完成后安装升级。
