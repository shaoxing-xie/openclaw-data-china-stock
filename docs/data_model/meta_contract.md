# 数据模型契约：`_meta` 与 `data_layer`

本文档为 **Phase 0** 单一事实源，与工具返回体中的 `_meta` 字段对齐。实现变更时先更新本文再改代码。

## `data_layer` 枚举（插件侧）

| 取值 | 含义 |
|------|------|
| `L1_raw` | 原始采集/接近上游结构 |
| `L2_entity` | 实体解析、主数据、代码归一 |
| `L3_feature` | 单标的因子/技术指标等标准化特征 |
| `L3_aggregate` | **复合、无投资建议**：多工具组合得分/排序/上下文，可审计 |
| `L3_composite` | 与 `L3_aggregate` 二选一作为全仓统一别名（当前以 `L3_aggregate` 为主） |
| `L4_data` | 确定性复合指标（分位、标签等），JSON Schema 约束；**禁止 advisory** |

**助手侧**：`L3_decision` / `L4_decision`（叙事、门闸、仓位、买卖建议）**不出现在插件工具 `_meta.data_layer`**。

## `schema_name` 约定

- 复合无建议输出：`rotation_feature_aggregate_v*`、`*_composite_v*`、`*_feature_aggregate_v*`
- **禁止**将上述输出命名为 `decision_*`（`decision_*` 保留给助手侧事件 schema）

## `_meta` 推荐字段

- `schema_name`, `schema_version`, `task_id`, `run_id`, `data_layer`
- `generated_at`, `trade_date`（如适用）
- `source_tools` / `lineage_refs`
- `quality_status`（与顶层 `quality_status` 一致或可说明从属关系）

## `entity_id`（L2 扩展）

- 规范见同目录 `entity_id.md`（逐步补全）。
- 过渡期：工具可同时返回 `canonical_code`（6 位等）与可选 `entity_id`。

## 多源 catalog 与运行时

- 见同目录 **`catalog_runtime_alignment.md`**（`factor_registry.yaml` 的 `source_chains` 与 `fetch_global` / 资金流 `_run_chain` 的合并规则、回滚与退出条件）。
