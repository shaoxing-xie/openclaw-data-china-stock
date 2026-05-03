# 安装与部署指南（openclaw-data-china-stock）

本指南面向“首次使用者 / 团队部署者”，目标是让用户快速找到、安装、验证插件。

## 1. 获取插件

推荐两种方式：

- **源码方式**：直接克隆仓库（适合开发与可定制部署）
- **打包方式**：使用发布包（例如仓库内 `.tgz` 产物，适合标准化分发）

## 2. 环境准备

- Python 3.10+
- 建议 Linux/macOS 使用 `python3`
- 建议每个部署实例使用独立 `.venv`

## 3. 源码安装（推荐）

```bash
cd /path/to/openclaw-data-china-stock
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
```

## 4. 关键依赖验证

```bash
python - <<'PY'
import talib, pandas_ta
print("talib ok")
print("pandas_ta ok")
PY
```

## 5. 解释器固定（强烈建议）

为避免多 Python 环境导致口径不一致：

```bash
export OPENCLAW_DATA_CHINA_STOCK_PYTHON="/abs/path/to/.venv/bin/python"
```

若 Gateway 由 **systemd --user** 启动且已 `EnvironmentFile=%h/.openclaw/.env`（常见），请把上述变量**写入 `~/.openclaw/.env`**，确保插件子进程与 CLI 使用同一解释器。

## 6. 最小验收

```bash
python -m pytest -q tests/test_manifest_tool_map_parity.py tests/test_tool_runner_dispatch.py tests/test_technical_indicators_tool.py
```

并执行一次真实数据 smoke（index/etf 任一标的）验证工具可用。

## 6.5 开发环境注册（让 OpenClaw 识别新增工具与 Skills）

如果你在本仓库内开发，并希望 **OpenClaw 直接使用开发目录的工具清单**，以及识别本仓库 Skills，可以执行：

```bash
.venv/bin/python scripts/register_openclaw_dev.py
```

该脚本会：

- 以“仅追加、不破坏原配置”的方式更新 `~/.openclaw/openclaw.json`
  - 将 `openclaw-data-china-stock` 插件 entry 配置指向本仓库的 `tool_runner.py` 与 `config/tools_manifest.json`
  - 将本仓库路径加入 `plugins.load.paths`
- 将以下 Skill 软链到 OpenClaw 工作区的 `skills/` 目录：
  - `china-macro-analyst`
  - `technical-analyst`
  - `market-scanner`
  - `market-sentinel`
  - `fund-flow-analyst`
  - `strategy-backtester`
  - `fundamental-analyst`
- 对 `workspace=/etf-options-ai-assistant` 的 agent 列表追加上述 skill 引用（若不存在）

## 7. 部署到运行目录（`~/.openclaw/extensions`）

若希望 Gateway **从扩展目录**加载插件（与开发克隆目录解耦），将仓库同步到运行目录后注册：

```bash
cd /path/to/openclaw-data-china-stock
bash scripts/install_plugin_to_runtime.sh
OPENCLAW_DATA_CHINA_STOCK_ROOT="${HOME}/.openclaw/extensions/openclaw-data-china-stock" \
  python3 "${HOME}/.openclaw/extensions/openclaw-data-china-stock/scripts/register_openclaw_dev.py"
```

说明：

- `install_plugin_to_runtime.sh` 使用 `rsync` 同步到默认目标 `~/.openclaw/extensions/openclaw-data-china-stock`（可用环境变量 `OPENCLAW_DATA_CHINA_STOCK_RUNTIME` 覆盖）。
- `register_openclaw_dev.py` 在未设置环境变量时，以**脚本所在仓库根**为插件根；设置 `OPENCLAW_DATA_CHINA_STOCK_ROOT` 后，**插件入口、`tool_runner.py`、`tools_manifest.json` 与 `skills/` 软链**均指向该目录。
- 交易助手 workspace `etf-options-ai-assistant` 下各 Agent 的 `skills` 会幂等追加本插件提供的 Skill（含 `market-sentinel`）；四情绪工具由插件 manifest 暴露，需在 **数据采集 Agent 白名单**中包含（见 `etf-options-ai-assistant` 文档「A 股情绪工具与 market-sentinel」）。

同步后请固定解释器（第 5 节）并重启 Gateway。

## 7.5 数据源健康探针与落盘路径

- **工具**：`tool_probe_source_health(write_snapshot=true)` 写入快照 `data/meta/source_health_snapshot.json`（若设置 **`OPENCLAW_DATA_DIR`**，则为 `$OPENCLAW_DATA_DIR/meta/`）。
- **事件**：`data/logs/source_events.jsonl`（探针事件与其它 source 事件）。
- **趋势**：每次快照成功后追加 `data/logs/source_health_probe_history.jsonl` 采样，并刷新聚合文件 `data/meta/source_health_history_rollup.json`（供助手 Chart Console `GET /api/semantic/data_source_health_history` 只读展示）。历史 JSONL 体积过大时会自动截断尾部保留。
- **干跑**：`write_snapshot=false` 不写盘、不写趋势采样。

## 8. 常见问题

- **出现 `TA-Lib 与 pandas-ta 均不可用`**
  - 当前解释器未装好依赖；按本指南第 3-5 步重装并固定解释器。
- **同机测试通过，服务运行失败**
  - 常见原因是运行时解释器不是你测试使用的 `.venv`。
