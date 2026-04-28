# Changelog

## 2026-04-28 (v0.5.5)

### Major: CNI + CSIndex daily collectors + release hygiene

- 新增双工具：
  - `tool_fetch_cni_index_daily`（AkShare `index_hist_cni`）
  - `tool_fetch_csindex_index_daily`（AkShare `stock_zh_index_hist_csindex`）
- 两工具统一输出契约：`success/message/data/count/source_id/source_raw/source_stage/quality_status/degraded_reason/attempts/elapsed_ms/task_id/run_id/_meta`。
- CNI 路径补充单位显式化与标准化输出：
  - 原始字段：`volume_raw(万手)`、`amount_raw(亿元)`
  - 标准字段：`volume(手)`、`amount(元)`
- 新增质量门禁与错误码：`INVALID_PARAM`、`DEPENDENCY_MISSING`、`UPSTREAM_ERROR`、`UPSTREAM_EMPTY`、`UPSTREAM_SCHEMA_DRIFT`、`NORMALIZE_FAILED`。
- 更新注册与文档：
  - `tool_runner.py`
  - `config/tools_manifest.{yaml,json}`
  - `plugins/data_collection/{README.md,DATA_SOURCE_REGISTRY.md,DATA_SOURCE_TOOL_INVENTORY.md}`
  - `plugins/data_collection/index/指数采集工具与原始接口说明.md`
- 新增测试与 smoke：
  - `tests/test_fetch_cni_daily.py`
  - `tests/test_fetch_csindex_daily.py`
  - `scripts/smoke_cni_csindex_daily.py`
- 发布包清理：`.clawhubignore` 排除 `.code-review-graph` 等本地开发产物，避免发布体积异常与安装失败。

## 2026-04-19 (v0.5.3)

### Major: `market-sentinel` skill (sentiment aggregate)

- 新增 Skill `skills/market-sentinel`：并行聚合 `tool_fetch_limit_up_stocks`、`tool_fetch_a_share_fund_flow`、`tool_fetch_northbound_flow`、`tool_fetch_sector_data`，输出 `overall_score`、`sentiment_stage`（含震荡/混沌）、`sub_scores`、`factor_attribution`、`data_completeness_ratio`、`action_bias`、`risk_counterevidence`、`confidence_band`、`degraded`；禁止具体买卖点与杠杆建议。
- 配置：`skills/market-sentinel/config/market-sentinel_config.yaml`（多 `risk_mode` 权重模板、`dynamic_weight_adjustment`、`sentiment_stage_thresholds`、聚合缓存 TTL）。
- 工具清单：上述四工具增加 `sentinel_bundle` / `skill_hint` 元数据；`scripts/register_openclaw_dev.py` 注册本 Skill 软链与 agent skills。
- 文档：`docs/sentiment/api_contract.md` 增补 Skill 聚合契约、阶段映射表、降级与 `insufficient_evidence` 形状；`docs/sentiment/examples.md` 增补 ≥5 条典型问法与端到端说明。
- 测试：`tests/test_market_sentinel_aggregate_contract.py` 与夹具 `tests/fixtures/sentiment/market_sentinel_aggregate_*.json`（契约与极端/降级场景）。

## 2026-04-18 (sentiment tools optimization closure)

### Major: four sentiment tools finalized

- 完成四个情绪类工具优化收口并统一工程规范：
  - `tool_fetch_limit_up_stocks`
  - `tool_fetch_a_share_fund_flow`
  - `tool_fetch_northbound_flow`
  - `tool_fetch_sector_data`
- 四工具统一接入响应契约与质量字段：`success/source/fallback_route/attempts/data_quality/cache_hit/error_code/explanation`。
- 明确并落地硬约束：**无上游且无缓存时直接失败，不生成估计值；缓存仅来自历史成功拉取结果**。

### Source chains and fallback policy

- `limit_up_pool` 链路定版：`akshare.stock_zt_pool_em -> stock_zt_pool_previous_em -> stock_zt_pool_strong_em -> stock_zt_pool_sub_new_em -> cache`。
- `fund_flow` 链路定版：THS-first（`stock_fund_flow_individual/concept/industry/big_deal`），东财兜底改为可选且默认关闭。
- `northbound` 链路定版：`tushare.moneyflow_hsgt -> eastmoney.legacy_hsgt -> cache`，移除 `stock_hsgt_fund_flow_summary_em`。
- `sector_snapshot` 链路定版：
  - industry: `ths_industry_summary -> sina.stock_sector_spot(新浪行业/行业) -> em_push2_industry -> akshare_industry_name_em -> cache`
  - concept: `sina.stock_sector_spot(概念) -> em_concept_clist -> em_concept_jsonp -> cache`

### Documentation and quality gates

- 新增/完善情绪文档体系：`docs/sentiment/api_contract.md`、`dq_policy.md`、`error_codes.md`、`akshare_interface_inventory.md`、`akshare_interface_validation_report.md`、`sentiment_data_object_call_chains.md`、`examples.md`。
- 更新项目主文档 `README.md` 与采集子文档 `plugins/data_collection/README.md`，同步四工具最终链路、硬约束和第三方接入入口。
- `tool_fetch_sector_data` 收口为链路内质量闸门执行（行业 `>=30`、概念 `>=10`、字段校验、null_ratio 校验），不通过即降级。

## 2026-04-17 (v0.5.1)

### Release preparation

- 按 ClawHub 发布规范完成发布前预检：版本一致性、工作区状态与关键 Skill 测试。
- 基于 v0.5.0 技能扩展内容进行补丁发布，确保仓库提交与 ClawHub 版本对齐。

## 2026-04-17 (v0.5.0)

### Major: paired tool + skill expansion

- 新增 5 个 Skill，完成“工具 + Skill”成对能力扩展：
  - `skills/technical-analyst`
  - `skills/market-scanner`
  - `skills/fund-flow-analyst`
  - `skills/strategy-backtester`（MVP）
  - `skills/fundamental-analyst`
- 与既有 `skills/china-macro-analyst` 共同形成 6 大分析方向（技术、扫描、资金、回测、基本面、宏观）。
- 新增统一规范文档：`skills/SKILL_CONTRACT.md`，统一 frontmatter、章节结构、输出契约与安全规则。

### Registration and manifest governance

- 升级 `scripts/register_openclaw_dev.py`，从单 Skill 注册扩展为 6 个 Skills 一次注册（含软链与 agent skills 绑定幂等处理）。
- 为核心工具补齐 `scope` / `tool_group` / `recommended` 标签，提升 Skill-Tool 边界机器可识别性：
  - 技术分析：`tool_calculate_technical_indicators`
  - 市场扫描：`tool_check_trading_status`、`tool_fetch_sector_data`、`tool_fetch_limit_up_stocks`
  - 资金流分析：`tool_fetch_a_share_fund_flow`、`tool_fetch_northbound_flow`
  - 基本面分析：`tool_fetch_stock_financials`、`tool_fetch_stock_financial_reports`
  - 跨域底座：`tool_fetch_market_data`

### Tests and docs

- 新增测试：
  - `tests/test_skill_metadata_integrity.py`
  - `tests/test_skill_tool_mapping.py`
  - `tests/test_skill_output_contract_smoke.py`
- 更新 `README.md` 与 `INSTALL.md`，补充 v0.5.0 单版本升级说明、6 个 Skill 导航与开发态注册说明。
- 版本统一升级到 `0.5.0`（`package.json` / `openclaw.plugin.json`）。

## 2026-04-17 (v0.4.3)

### Documentation refinement

- 重构 `README.md` 与 `README_EN.md` 为统一的信息架构（痛点、核心能力、快速开始、运行说明、测试与贡献），提高首次阅读和接入效率。
- 增补 ClawHub 安装兼容命令（带/不带 `clawhub:` 前缀）与可点击的 GitHub Issues 链接，降低不同 CLI 版本下的安装与反馈门槛。

## 2026-04-17 (v0.4.2)

### Critical fix: tail-session compatibility restore

- 新增 `plugins/data_collection/index/fetch_global_hist_sina.py` 兼容模块，恢复历史导入路径 `plugins.data_collection.index.fetch_global_hist_sina`，修复尾盘链路因模块缺失导致的工具执行失败。
- 增加全局指数符号别名与回退候选（如 `^N225` / `^IXIC`），并在历史接口失败时返回结构化失败结果，避免异常向上冒泡影响报告主流程。

## 2026-04-17 (v0.4.1)

### Security and release hygiene

- 移除 `plugins/data_collection/utils/ths_big_deal_limited.py` 中的动态 JS 执行路径，改为直接复用 AkShare 接口并本地限流截断，降低供应链与静态扫描风险。
- 强化 `.clawhubignore`，排除 `.pytest_cache/`、`tool_test_report*.json` 与 `*.tgz`，减少发布包噪音与误报。

## 2026-04-17 (v0.4.0)

### Major: China Macro Analyst integration

- 新增宏观采集模块 `plugins/data_collection/macro/`，提供统一入口 `tool_fetch_macro_data` 与快照入口 `tool_fetch_macro_snapshot`。
- 新增 21 个兼容宏观工具 `tool_fetch_macro_*`，内部统一路由到 dataset 契约。
- 工具返回统一暴露数据质量字段：`as_of`、`staleness_days`、`data_lag_days`、`revision_policy`、`warnings`。
- 新增 Skill：`skills/china-macro-analyst`，采用机构化四段叙事模板并外置规则到 `macro_config.yaml`。
- 新增第三方接入文档：`docs/macro/api_contract.md`、`docs/macro/error_codes.md`、`docs/macro/dq_policy.md` 与 `examples/macro/*.json`。

### Quality and tests

- 新增测试：`tests/test_macro_tools.py`、`tests/test_macro_skill.py`。
- 保持 manifest/tool_runner 对齐，新增宏观工具后仍可通过 parity 校验。

## 2026-04-16

### Major Upgrade: Technical Indicators Expansion

- 新增并完成 `tool_calculate_technical_indicators` 的 P0/P1/P2 全量实现。
- 指标总数扩展至 **58**：
  - P0: 19
  - P1: 10
  - P2: 29（CDL 形态识别 20 + 统计 6 + 波动补充 3）
- 引擎策略完善：`TA-Lib` 优先，`pandas-ta` 自动降级，`builtin` 最后兜底。
- 新增结构化错误码：`UPSTREAM_EMPTY_DATA`。
- 完善解释器解析策略（支持环境变量优先 + 本地 `.venv` 自动发现）。
- 文档体系升级：
  - `README.md`（产品化入口）
  - `INSTALL.md`（安装部署指南）
  - 指标文档增加字段对照表与 P2 说明

### Patch: restore full tool registration (compat)

- 将 `config/tools_manifest.{json,yaml}` 与 `tool_runner.py` 恢复为全量工具清单，保证历史工具仍可被 OpenClaw 正常发现与执行。
- 重新加入并映射 `tool_calculate_technical_indicators` 到新增的技术指标引擎实现，支持 P0/P1/P2（共 58 指标）。

### Validation

- 指标工具、manifest/tool_runner 对齐测试全部通过。
- 真实行情 smoke 验证通过（含 P2 字段）。
