# openclaw-data-china-stock

OpenClaw 中国市场数据插件（A股 / ETF / 期权 / 资金流 / 技术指标）。  
当前版本已覆盖 `tool_calculate_technical_indicators` 的 **P0+P1+P2 全量 58 指标**，可直接用于研究、监控与策略流水线。

## 你可以用它做什么

- **统一行情入口**：`tool_fetch_market_data` 拉取 index/etf/stock/option 多资产视图
- **缓存读取入口**：`tool_read_market_data`
- **技术指标引擎**：`tool_calculate_technical_indicators`（58 指标，TA-Lib 优先）
- **A股专题工具**：资金流、技术选股、盘前/分时/估值快照、板块轮动等
- **宏观工具（v0.4.0）**：`tool_fetch_macro_data` / `tool_fetch_macro_snapshot` + 21 个兼容宏观入口

## 获取与安装

优先看：`INSTALL.md`（包含“源码安装 / 打包安装 / 环境变量配置 / 验收命令”）。

### 快速安装（源码方式）

```bash
cd /path/to/openclaw-data-china-stock
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

验证关键依赖：

```bash
python - <<'PY'
import talib, pandas_ta
print("talib ok")
print("pandas_ta ok")
PY
```

## 核心能力升级（本次）

- 新增并完成 `tool_calculate_technical_indicators` 的 P0/P1/P2：
  - P0（19）：趋势/动量/波动最小完备集
  - P1（10）：成交量与趋势扩展
  - P2（29）：形态识别（20）+ 统计（6）+ 波动补充（3）
- 引擎策略：`TA-Lib` -> `pandas-ta` -> `builtin`
- 支持 `append/standalone` 双输出模式
- 提供结构化错误码：`VALIDATION_ERROR` / `UPSTREAM_EMPTY_DATA` / `UPSTREAM_FETCH_FAILED` / `RUNTIME_ERROR`

详细字段映射见：`plugins/data_collection/technical_indicators/README.md`

## Macro Analyst (v0.4.0)

- 新增目录：`plugins/data_collection/macro/`
- 统一入口：
  - `tool_fetch_macro_data(dataset, latest_only, lookback, frequency)`
  - `tool_fetch_macro_snapshot(scope, include_quadrant)`
- 兼容入口：`tool_fetch_macro_*`（保留给旧工作流）
- 新增 Skill：`skills/china-macro-analyst/SKILL.md`
- 新增对外文档：
  - `docs/macro/api_contract.md`
  - `docs/macro/error_codes.md`
  - `docs/macro/dq_policy.md`
- 新增开发环境一键注册脚本：
  - `scripts/register_openclaw_dev.py`（把开发目录的 tool_runner/manifest 注册进 OpenClaw，并把 Skill 暴露到 OpenClaw workspace）

## OpenClaw 开发环境快速注册（推荐）

如果你是在本仓库内开发并希望 **OpenClaw 立即识别新增工具与 Skill**，执行：

```bash
.venv/bin/python scripts/register_openclaw_dev.py
```

它会以“仅追加、不破坏原配置”的方式更新 `~/.openclaw/openclaw.json`，并将
`skills/china-macro-analyst` 软链到 OpenClaw 工作区的 `skills/` 目录中。

## 工具推荐与分组（面向第三方）

宏观工具在 manifest 中提供可机读标签：

- `scope`: `china_macro_analyst` / `legacy`
- `recommended`: `true|false`
- `tool_group`: `primary_macro` / `macro_compat` / `adjacent_legacy_macro`

第三方接入默认只用 `primary_macro`（`tool_fetch_macro_data` / `tool_fetch_macro_snapshot`）。

## Python 解释器优先级（跨环境可复用）

插件执行 Python 工具时按以下顺序解析：

1. `OPENCLAW_DATA_CHINA_STOCK_PYTHON`
2. 插件目录 `.venv`（Linux/macOS/Windows）
3. 当前工作目录 `.venv`
4. 兼容旧路径（home/pipx）
5. `python3` 兜底

如需强制指定：

```bash
export OPENCLAW_DATA_CHINA_STOCK_PYTHON="/abs/path/to/python"
```

## 文档导航

- 安装与部署：`INSTALL.md`
- 指标工具明细：`plugins/data_collection/technical_indicators/README.md`
- 发布说明：`CHANGELOG.md`

## 回归测试

```bash
python -m pytest -q tests/test_manifest_tool_map_parity.py tests/test_tool_runner_dispatch.py tests/test_technical_indicators_tool.py
```

