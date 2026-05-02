# P0 日志基线（§三 实证补充 · 可重复执行）

本文件落实规划 **P0 日志基线**：在 **不修改规划正文** 的前提下，为 `~/.openclaw`、cron、Gateway 工具 JSON 提供 **抽样方法与聚合维度**，便于按 `source_id` / `source_interface` 归因。

## 1. 抽样位置（运行环境）

| 来源 | 路径 / 动作 | 备注 |
|------|-------------|------|
| OpenClaw 环境 | `~/.openclaw/.env`（仅检查键是否存在，勿打印密钥） | 与 cron 预检一致：`set -a; source ~/.openclaw/.env` |
| Cron | `~/.openclaw/cron/jobs.json` 中调用 `tool_runner` / `openclaw-data-china-stock` 的条目 | 关注 `stderr` 重定向文件（若配置） |
| Gateway / 工具返回 | 工具 JSON 中 `success: false`、`quality_status: degraded|error`、`message`、`error_code`、`attempts` | 优先从 `attempts[].source_id` / `source_interface` 聚合 |

## 2. 聚合维度（与 REGISTRY / CONNECTORS 对齐）

- **主键**：`source_id`（canonical）+ `source_interface`（若存在）+ `error_code`。
- **计数**：近窗（如 7d）内失败次数、degraded 次数。
- **输出**：是否需扩展全库 **`error_code`** 清单（参见 `docs/sentiment/error_codes.md` 扩展思路）。

## 3. 实证表示例（手工或脚本填写）

| source_id（或 unknown） | source_interface（样例） | 现象（HTTP/429/空帧） | 近窗计数（占位） | 建议 error_code / 动作 |
|-------------------------|--------------------------|----------------------|------------------|-------------------------|
| sina | `sina.http.*` | 403/502（全球指数链路等） | 待填 | `UPSTREAM_FETCH_FAILED` / 降频 |
| eastmoney | `eastmoney.*` | 限流 / 空表 | 待填 | 与附录 B 间隔叠加 |
| yfinance | `yfinance.*` | 代理隧道失败 | 待填 | 校验 `per_source` 代理 |
| tushare | `tushare.*` | 积分/权限与表二分钟 | 待填 | §5.1 `permission_profile` |
| （待抽样） | | | | |

## 4. 建议的一键抽样命令（在运维机执行）

```bash
# 仅示例：按任务日志路径调整
rg -n "success.: false|quality_status.: .(degraded|error)" ~/.openclaw/logs 2>/dev/null | head -200
```

将输出粘贴到上表「现象」列或附件 issue，并在 **CONNECTORS** 变更说明中引用本文件日期。
