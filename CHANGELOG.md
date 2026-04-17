# Changelog

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
