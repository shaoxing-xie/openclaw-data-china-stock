---
name: market-sentinel
description: 市场情绪哨兵，聚合涨停/资金/北向/板块四源，输出综合评分、阶段判定与反证（非交易指令）。
version: 1.0.0
author: shaoxing-xie
tags:
  - market
  - sentiment
  - aggregate
  - risk
triggers:
  - 市场情绪
  - 情绪阶段
  - 综合情绪
  - 冰点高潮
  - 情绪评分
  - 北向资金情绪
---

# Market Sentinel

## 目标

在单日或短回溯窗口内，对 A 股市场情绪做**可解释的综合评估**：综合分、阶段标签、主导因子与风险反证；不替代扫描类 Skill。

## 输入

- 用户问题（可含 `date`、`lookback_days`、`risk_mode`）
- 四类情绪工具返回的结构化证据

## 输出（固定结构）

1. 综合分与阶段（0–100 分 + 冰点/修复/高潮/退潮/震荡/混沌）
2. 子项分数与主导因子归因
3. 数据完整性比例与（如有）降级说明
4. 行动倾向框架与置信带

## 强制规则

- **必须并行调用**四个依赖工具（异步/并发），禁止为省事串行阻塞；聚合结果可按 `config/market-sentinel_config.yaml` 的短 TTL 缓存复用。
- 核心证据不足以支撑结论时，输出 `insufficient_evidence` 并说明缺失项。
- 禁止输出具体买卖点、仓位比例、杠杆建议。
- 权重、`risk_mode`、动态调权规则仅从 `config/market-sentinel_config.yaml` 读取。

## 依赖工具

- `tool_fetch_limit_up_stocks`
- `tool_fetch_a_share_fund_flow`
- `tool_fetch_northbound_flow`
- `tool_fetch_sector_data`

## 通用输出字段

- `overall_score`
- `sentiment_stage`
- `sub_scores`
- `factor_attribution`
- `data_completeness_ratio`
- `action_bias`
- `risk_counterevidence`
- `confidence_band`
- `degraded`
