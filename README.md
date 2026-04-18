# openclaw-data-china-stock

为 OpenClaw 打造的中国市场数据底座：覆盖 A 股、ETF、指数、期权、资金流、技术指标与宏观分析。

[![GitHub release](https://img.shields.io/github/v/release/shaoxing-xie/openclaw-data-china-stock)](https://github.com/shaoxing-xie/openclaw-data-china-stock/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Plugin-blue)](https://openclaw.ai/)

一句话概述：为 OpenClaw Agent 提供统一行情采集、58 指标计算，并以“工具+Skill”成对输出投研能力。

## v0.5.0 升级亮点（单版本）

- 新增 5 个 Skill，与现有宏观 Skill 组成 6 大分析方向：
  - `technical-analyst`
  - `market-scanner`
  - `fund-flow-analyst`
  - `strategy-backtester`（MVP 轻回测编排）
  - `fundamental-analyst`
  - `china-macro-analyst`（既有）
- 能力结构从“工具可调用”升级为“工具 + Skill 可直接消费”：
  - 工具层负责数据采集与计算
  - Skill 层负责结构化分析、证据约束、风险反证与统一输出契约
- 发布策略：本次 5 个 Skill 一次性升级发布（非分步小版本）

## 为什么你会需要它

在 A 股量化/投研工作流里，常见痛点通常是：

- 单一数据源不稳定，接口变动后维护成本高
- 指标实现繁琐，跨环境依赖不一致（TA-Lib/pandas-ta）
- 指标口径与本地行情软件不一致，难以校验
- 宏观数据收集分散，难以快速形成结构化结论
- 采集、分析、Agent 调用链路割裂，难以自动化

这个项目的目标是将上述问题收敛为一个可复用、可扩展、可直接被 Agent 调用的插件层。

## 核心能力

### 1) 全资产行情采集

- 统一入口：`tool_fetch_market_data`（index/etf/stock/option）
- 缓存读取：`tool_read_market_data`
- A 股专题：资金流、技术选股、盘前分时、估值快照、板块轮动等
- 多源回退与容错：降低单源故障对工作流的影响

### 2) 技术指标引擎（58 指标）

- 工具：`tool_calculate_technical_indicators`
- P0/P1/P2 全量共 58 指标（趋势、动量、波动、形态、统计）
- 引擎优先级：`TA-Lib -> pandas-ta -> builtin`
- 输出模式：`append` / `standalone`
- 结构化错误码：`VALIDATION_ERROR` / `UPSTREAM_EMPTY_DATA` / `UPSTREAM_FETCH_FAILED` / `RUNTIME_ERROR`

详见：`plugins/data_collection/technical_indicators/README.md`

### 3) 宏观数据与分析（v0.4.0+）

- 统一宏观入口：
  - `tool_fetch_macro_data(dataset, latest_only, lookback, frequency)`
  - `tool_fetch_macro_snapshot(scope, include_quadrant)`
- 兼容入口：`tool_fetch_macro_*`（兼容旧工作流）
- 宏观 Skill：`skills/china-macro-analyst/SKILL.md`
- 对外契约与数据质量文档：
  - `docs/macro/api_contract.md`
  - `docs/macro/error_codes.md`
  - `docs/macro/dq_policy.md`

### 4) Skill 能力层（v0.5.0+）

- 技术分析：`skills/technical-analyst/SKILL.md`
- 市场扫描：`skills/market-scanner/SKILL.md`
- 资金流分析：`skills/fund-flow-analyst/SKILL.md`
- 策略回测（MVP）：`skills/strategy-backtester/SKILL.md`
- 基本面分析：`skills/fundamental-analyst/SKILL.md`
- 宏观分析（既有）：`skills/china-macro-analyst/SKILL.md`
- 统一规范：`skills/SKILL_CONTRACT.md`

### 5) 四个情绪工具（已完成优化收口）

- 覆盖工具：
  - `tool_fetch_limit_up_stocks`
  - `tool_fetch_a_share_fund_flow`
  - `tool_fetch_northbound_flow`
  - `tool_fetch_sector_data`
- 统一能力：
  - 多源降级链 + 质量闸门（结构/规模/null_ratio）
  - 统一响应契约（`success/source/fallback_route/attempts/data_quality/explanation`）
  - 交易时段差异化 TTL 缓存（盘中/盘后/日终）
  - 衍生指标本地计算（不污染上游原始数据）
- 明确原则：
  - **无上游且无缓存时直接失败，不生成估计值**
  - 缓存仅来自历史成功拉取结果，不做虚构填补
- 关键链路（已拍板）：
  - `limit_up_pool`: `akshare.stock_zt_pool_em -> stock_zt_pool_previous_em -> stock_zt_pool_strong_em -> stock_zt_pool_sub_new_em -> cache`
  - `fund_flow`: `THS-first`（东财兜底可选且默认关闭）
  - `northbound`: `tushare.moneyflow_hsgt -> eastmoney.legacy_hsgt -> cache`
  - `sector_snapshot`:
    - industry: `ths_industry_summary -> sina.stock_sector_spot(新浪行业/行业) -> em_push2_industry -> akshare_industry_name_em -> cache`
    - concept: `sina.stock_sector_spot(概念) -> em_concept_clist -> em_concept_jsonp -> cache`
- 详细文档：
  - `docs/sentiment/api_contract.md`
  - `docs/sentiment/dq_policy.md`
  - `docs/sentiment/error_codes.md`
  - `docs/sentiment/akshare_interface_inventory.md`
  - `docs/sentiment/akshare_interface_validation_report.md`
  - `docs/sentiment/sentiment_data_object_call_chains.md`
  - `docs/sentiment/examples.md`

### 6) 面向 OpenClaw Agent 的工程化集成

- `config/tools_manifest.json` + `tool_runner.py` 统一路由
- 支持开发态快速注册：`scripts/register_openclaw_dev.py`
- 解释器解析优先级明确，便于跨环境部署

## 快速开始

优先参考：`INSTALL.md`（源码安装 / 打包安装 / 环境变量 / 验收命令）。

### 安装方式（ClawHub）

```bash
openclaw plugins install clawhub:@shaoxing-xie/openclaw-data-china-stock
```

如你的 OpenClaw CLI 版本不支持 `clawhub:` 前缀，可改用：

```bash
openclaw plugins install @shaoxing-xie/openclaw-data-china-stock
```

### 安装方式（源码开发）

```bash
cd /path/to/openclaw-data-china-stock
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

如你的网络环境对 AKShare 东方财富链路有额外限制，可按需安装可选增强依赖（非必需）：

```bash
python -m pip install -r requirements-optional.txt
```

### 开发环境一键注册（推荐）

```bash
.venv/bin/python scripts/register_openclaw_dev.py
```

该脚本会以“仅追加、不破坏原配置”的方式更新 `~/.openclaw/openclaw.json`，并将相关 skill 暴露到 OpenClaw workspace。

## 常见使用示例（Agent 指令）

- “请拉取 510300 最近一年日线并计算 RSI、MACD、布林带。”
- “请给出今日 A 股资金流最强行业和对应 ETF。”
- “请输出最新宏观快照，并判断当前美林时钟象限。”
- “请做一份 510300 技术面分析，输出趋势/动量/波动和风险反证。”
- “请扫描当前盘中市场，给出情绪阶段与异动清单。”
- “请解读今天主力与北向资金是否共振。”
- “请给出贵州茅台基本面四维评分和估值偏离。”
- “请对 510300 的均线策略做回测评估，并说明当前是 MVP 模式限制。”

## 文档导航

- 安装与部署：`INSTALL.md`
- 技术指标明细：`plugins/data_collection/technical_indicators/README.md`
- Skill 总规范：`skills/SKILL_CONTRACT.md`
- 技术分析 Skill：`skills/technical-analyst/SKILL.md`
- 市场扫描 Skill：`skills/market-scanner/SKILL.md`
- 资金流分析 Skill：`skills/fund-flow-analyst/SKILL.md`
- 策略回测 Skill：`skills/strategy-backtester/SKILL.md`
- 基本面分析 Skill：`skills/fundamental-analyst/SKILL.md`
- 宏观 Skill：`skills/china-macro-analyst/SKILL.md`
- 宏观 API / 错误码 / 数据质量：
  - `docs/macro/api_contract.md`
  - `docs/macro/error_codes.md`
  - `docs/macro/dq_policy.md`
- 版本发布记录：`CHANGELOG.md`

## 兼容性与已知限制

- 兼容旧流程：`tool_fetch_macro_*` 兼容入口仍保留。
- `strategy-backtester` 当前为 MVP 编排模式：
  - 基于 `tool_fetch_market_data` + `tool_calculate_technical_indicators`
  - 未引入独立 `tool_backtest_*` 专用工具链
  - 输出会显式声明能力边界与限制

## 回归测试

完整测试：

```bash
python -m pytest -q tests/
```

最小关键链路测试：

```bash
python -m pytest -q tests/test_manifest_tool_map_parity.py tests/test_tool_runner_dispatch.py tests/test_technical_indicators_tool.py
```

## 运行说明

### 缓存策略

默认 `data_cache.enabled=false`：

- 允许读取已有缓存文件
- 默认不写入新的 parquet 缓存

仅在需要本地读写缓存时，将 `config.yaml` 中 `data_cache.enabled` 设为 `true`。

### 返回字段约定

大多数工具返回：

- `success`
- `data`
- `message`
- `source`

部分工具会补充 `count`、`timestamp`、`cache_hit`、`provider`、`fallback_route`、`attempt_counts` 等字段，用于排障和可观测性。

四个情绪工具额外统一遵循：
- `data_quality`: `fresh | cached | partial`
- `attempts`: 每个上游源调用结果
- `used_fallback`: 最终命中是否为降级路径
- `error_code/error_message`: 上游失败可诊断信息
- `explanation`: 可读解释（供第三方直接消费）

## 贡献

欢迎提交 Issue / PR：

- 发现问题或提需求：[GitHub Issues](https://github.com/shaoxing-xie/openclaw-data-china-stock/issues)
- 提交改进：基于 `main` 发起 PR

## 许可证

MIT

## 免责声明

本项目用于数据采集与技术研究，不构成投资建议。

## 致谢

宏观与行情生态能力基于开源社区（如 AKShare）提供的数据接口与工程实践。

