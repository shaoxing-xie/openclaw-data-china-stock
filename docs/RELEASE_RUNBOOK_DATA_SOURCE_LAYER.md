# 数据源封装层 — 发布与验证 Runbook（§八）

## 阶段一（插件）

```bash
set -a; source /home/xie/.openclaw/.env || true; set +a
cd /home/xie/openclaw-data-china-stock
./.venv/bin/python -m pytest tests/ -q --tb=no -x
```

## 阶段二（助手）

```bash
set -a; source /home/xie/.openclaw/.env || true; set +a
cd /home/xie/etf-options-ai-assistant
./.venv/bin/python -m pytest tests/test_etf_rotation_core.py tests/test_rotation_data_readiness.py -q --tb=no
```

## clawhub 发布（运维执行）

在插件开发目录（需 Node + clawhub CLI + 网络）：

```bash
cd /home/xie/openclaw-data-china-stock
clawhub package publish "$(pwd)" \
  --family code-plugin \
  --version "$(node -p "require('./package.json').version")" \
  --source-repo shaoxing-xie/openclaw-data-china-stock \
  --source-ref main \
  --source-commit "$(git rev-parse HEAD)"
```

安装到 `~/.openclaw/extensions/openclaw-data-china-stock` 后核对 `openclaw.plugin.json` 与 `.venv`。

### clawhub → `openclaw plugins install` 若报 missing `.clawhubignore`

部分 registry 校验会对 tarball 与 `files[]` 元数据比对；若 `clawhub:@scope/name@version` 安装失败并提示缺少 `.clawhubignore`，可在插件根目录用 **与发布相同的树** 打本地包并安装（等价于从已发布版本号对应的源码安装）：

```bash
cd /home/xie/openclaw-data-china-stock
npm pack   # 确认输出包内含 package/.clawhubignore
openclaw plugins install "$(pwd)/$(npm pack | tail -1)" --force
```

安装器会为插件创建/更新 `~/.openclaw/extensions/openclaw-data-china-stock`；**Python 依赖**通常使用你在 `openclaw.json` / 环境变量中配置的解释器（例如 `OPENCLAW_DATA_CHINA_STOCK_PYTHON` 指向开发仓 `.venv`），扩展目录内未必自带 `.venv`，以 `openclaw plugins list` / `doctor` 为准。

## 阶段三（生产）

- Gateway 抽样 `tool_read_market_data` / `tool_fetch_index_data`；cron 关键任务；`GET /api/semantic/data_source_health`。
- 对比升级前后 `quality_status` 与日志量；准备版本 pin / 回滚说明。
