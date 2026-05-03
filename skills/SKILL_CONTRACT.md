# Skill Contract (openclaw-data-china-stock)

This document defines the shared contract for all skill assets in this repository.

## Directory layout

Each skill must follow:

- `skills/<skill-name>/SKILL.md`
- `skills/<skill-name>/README.md`
- `skills/<skill-name>/config/<skill-name>_config.yaml`
- `skills/<skill-name>/references/*.md`

## Required frontmatter fields

All `SKILL.md` files must include:

- `name`
- `description`
- `version`
- `author`
- `tags`
- `triggers`

## Required sections

All `SKILL.md` files must include:

- `## 目标`
- `## 输入`
- `## 输出（固定结构）`
- `## 强制规则`
- `## 依赖工具`
- `## 通用输出字段`

## Shared safety rules

- Data first, interpretation second.
- No direct execution instructions (position, leverage, buy/sell timing).
- If core evidence is missing, output `insufficient_evidence`.
- Explain key risk counterevidence and confidence band.
- Thresholds/policies must be read from per-skill config files, not hardcoded in narrative.

## Data layer boundary (L3 / L4-data vs Skill vs L4-decision)

- **L3 / L4-data（插件工具 JSON）**：可复现数值、因子、复合指标（分位、标签、得分等）的 **单一事实源**。Skill **不得**把关键数值仅写在叙述段而无工具引用或附录结构化摘要。
- **Skill（本仓库）**：可读分析、**证据约束**、**风险反证**、叙事组织；可引用工具返回中的 `_meta`、`quality_status`、`lineage_refs` / `source_tools`。
- **L4-decision（助手 / 上层）**：投资建议、仓位、门闸与产品化 UI 语义视图；**不在本插件 Skill 正文输出**（禁用「建议买入/卖出/加仓/目标价/评级驱动仓位」等 advisory 话术）。

## Tool invocation discipline

- Skills **must** instruct callers to use **manifest 注册工具** via OpenClaw `tool_runner` / 网关工具列表路径获取数据。
- **禁止**引导在 Skill 流程中 **绕过工具层** 直接 `import` 或调用 `plugins.data_collection.*` 采集实现（避免双口径与无血缘）。

## Recommended output annex (Phase A)

在 `## 输出（固定结构）` 下鼓励增加子节：

- **`### 证据表`**：列出已调用的 `tool_*`、关键字段快照或 `success/quality_status`。
- **`### 反证与局限`**：数据缺口、源降级、`degraded` 说明。
- **（可选）结构化摘要**：与工具 JSON 对齐的小块 YAML/JSON，便于下游程序化消费。

契约全文与枚举见：`docs/data_model/meta_contract.md`。

