# 多 Skill 编排（Step B 参考）

## 目标

在 Agent 会话中 **顺序或并行** 调用多个本仓库 Skill 时，统一合并输出与冲突处理。

## 推荐模式（类 TEAM_RESULT）

1. **分工**：每个 Skill 只承担其 `SKILL.md` 边界（如 `technical-analyst` 不负责资金流）。
2. **事实层**：先拉齐 L3/L4-data 工具 JSON，再进入各 Skill 叙述。
3. **合并字段**：建议外层结构 `{ "skills": [...], "evidence_index": [...], "conflicts": [] }`。
4. **冲突**：同一指标不同工具结论时，写入 `conflicts` 并降低 `confidence_band`，不得强行二选一叙事。

## 禁止

- 绕过 `tool_runner` / manifest 直接 import 采集实现。
- 在合并层输出买卖/仓位建议（划归助手 L4-decision）。
