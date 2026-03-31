# openclaw-data-china-stock

**面向 A 股个人投资者的 OpenClaw / ClawHub 行情数据底座**

开源、免费的 OpenClaw / ClawHub **代码插件**，为指数、ETF、个股与挂牌期权提供**统一 `tool_*` 接口**、多数据源优先级与降级，以及默认安全的磁盘缓存策略（`data_cache.enabled=false`：可读已有 Parquet、默认不写盘）。

**一句话**：少在「接口不稳定、格式不统一、缓存难控」上踩坑，把时间留给策略与工程，而非和数据源纠缠。

---

### 核心亮点

- **统一入口**：优先使用 `tool_fetch_market_data`，跨指数 / ETF / 股票 / 期权（支持 `realtime` / `historical` / `minute` / `opening` / `greeks` 等 `view`）。
- **多源降级**：AkShare、新浪、东方财富、可选 Tushare 等按配置优先级与熔断/重试协作，降低单点不可用对 Agent 工作流的影响。
- **缓存可控**：默认关闭磁盘 Parquet **写入**，避免脏数据污染；需要离线补数时再在 `config.yaml` 中开启 `data_cache.enabled=true`。
- **散户常用能力**：涨停池、龙虎榜、北向资金、板块热度、期权 Greeks、交易状态与合约查询等（以 `config/tools_manifest.json` 注册为准）。
- **契约一致**：多数工具返回带 `success` / `data` / `message` / `source` 的 JSON，便于 Agent 编排。

---

### 安装

**从 ClawHub / 注册表安装（推荐）**

若一种命令失败，可尝试另一种（取决于 OpenClaw 版本与 CLI）：

```bash
openclaw plugins install clawhub:@shaoxing-xie/openclaw-data-china-stock
```

```bash
openclaw plugins install @shaoxing-xie/openclaw-data-china-stock
```

安装或更新插件后，请按你本机方式**重启 OpenClaw Gateway**（或等价服务），再在 Dashboard / `openclaw status` 中确认插件与工具已加载。

**从 GitHub 克隆（本地调试 / 贡献代码）**

```bash
git clone https://github.com/shaoxing-xie/openclaw-data-china-stock.git
cd openclaw-data-china-stock
pip install -r requirements.txt
```

将本仓库作为扩展挂载的方式以你本机 OpenClaw 文档为准；常见做法包括把插件目录复制/链接到 `extensions` 并在 `openclaw.json` 中允许该插件，或执行 `openclaw plugins install --help` 查看是否支持**路径安装 / 符号链接**。

---

### 三分钟上手

1. 在 OpenClaw 插件配置中确认 `scriptPath` 指向包内的 `tool_runner.py`（默认通常即可）。
2. 在 Agent / Workflow 中**优先**调用统一入口 `tool_fetch_market_data`。
3. 离线或弱网场景可配合 `tool_read_market_data` 及各类 `tool_read_*`（依赖已有缓存文件）。

**指数日线历史示例：**

```yaml
tools:
  - name: tool_fetch_market_data
    params:
      asset_type: index
      view: historical
      asset_code: "000001"
      period: daily
      start_date: "20260201"
      end_date: "20260228"
```

**沪深 300 ETF 5 分钟线：**

```yaml
tools:
  - name: tool_fetch_market_data
    params:
      asset_type: etf
      view: minute
      asset_code: "510300"
      period: "5"
      start_date: "20260201"
      end_date: "20260228"
```

**期权 Greeks：**

```yaml
tools:
  - name: tool_fetch_market_data
    params:
      asset_type: option
      view: greeks
      contract_code: "10010910"
```

**更多能力（示例）**：涨停池 `tool_fetch_limit_up_stocks`、北向 `tool_fetch_northbound_flow`、龙虎榜 `tool_dragon_tiger_list`（完整列表见下文）。

### Tushare 备份配置

部分数据源会以 Tushare 作为可选兜底：请设置环境变量 `TUSHARE_TOKEN`（或在 `config.yaml` 的 `tushare.token` 中配置）。

---

### 缓存策略（默认语义）

默认 `data_cache.enabled=false` 时：插件会**允许读取**已有磁盘 Parquet 缓存，但**跳过磁盘 Parquet 写入**（降低生成/覆盖文件带来的污染风险）。写入与详细语义见下文「缓存策略（重要）」。

---

### 你能获得什么

本插件包含 `data_collection` 与 `merged` 的工具实现，并对外提供稳定的 `tool_*` 接口，覆盖：

- 指数 / ETF / 个股 / 期权市场数据（实时、历史、分钟、开盘、Greeks 等）。
- 期权合约列表（按 underlying）。
- 可选：盘前/政策/news、行业轮动、涨停池、北向资金等（以清单为准）。
- 可选：本地 Parquet 缓存读取。

---

### 为何需要、适合谁

许多个人投资者不缺零散信息，而缺一套**口径相对统一、可用性更可预期**的数据层：多源格式不一、单接口限流或故障、缓存难审计。本插件用统一参数与返回约定，加上多源优先级与降级，把工作流里的「取数」收敛为一组可维护的 `tool_*`。

- 以 A 股 / ETF / 期权为主要研究对象的个人用户  
- 希望把「盯盘 → 取数 → 分析」流程化、自动化的用户  
- 希望在 OpenClaw 上二次开发、但不愿在采集层反复踩坑的开发者  

---

### 免责声明

本插件仅用于**数据采集与技术研究**，不构成任何投资建议或收益承诺。任何使用行为及后果由使用者自行承担。

---

### 推荐的使用方式

1. 插件设置中确认 `tool_runner.py` 路径（包内默认布局下一般无需改）。  
2. Agent / Workflow 中优先调用 `tool_fetch_market_data`。  
3. 需要依赖本地缓存读取时：使用 `tool_read_market_data` 或 `tool_read_index_*` / `tool_read_etf_*` / `tool_read_option_*`；需要写入 Parquet 时在配置中显式开启 `data_cache.enabled=true` 并理解路径与磁盘占用。  

---

### 背景与用途

`openclaw-data-china-stock` 面向 A 股市场数据采集：围绕指数、ETF、个股与挂牌期权，为 OpenClaw 工作流提供统一 `tool_*` 接口；默认不写入磁盘缓存（由 `config.yaml` 中 `data_cache.enabled` 控制），适合「在线抓取优先 + 已有缓存可读」。

---

### 面向散户的痛点与解决方案

- **覆盖广**：指数、ETF、A 股个股、挂牌期权等多类资产的实时/历史/分钟级行情与合约查询。  
- **多源更稳**：内置 provider 优先级与自动降级。  
- **缓存可控**：默认关闭磁盘缓存写入；需要时再显式开启。  
- **统一入口**：`tool_fetch_market_data` 为主，兼容 `tool_fetch_index_data` / `tool_fetch_etf_data` / `tool_fetch_option_data`。  

---

### 工具分类与接口清单（用于讨论首发暴露范围）

说明：以下 `tool_id` 来自本仓库 `config/tools_manifest.yaml`（运行时以 `config/tools_manifest.json` 注册为准）。
其中「已注册」表示当前版本已在 OpenClaw 中暴露，直接可被工具调用；「未纳入当前首发清单」表示在本仓库代码中可能存在，但尚未纳入当前工具清单（需要后续版本补齐）。

#### 跨资产统一入口（推荐）

- `tool_fetch_market_data`（已注册）
  - `asset_type=realtime|historical|minute|opening|greeks|global_spot|iopv_snapshot` 维度统一入口（配合 `asset_code/contract_code` 等参数）

#### 兼容入口（merged 三入口）

- `tool_fetch_index_data`（已注册）
- `tool_fetch_etf_data`（已注册）
- `tool_fetch_option_data`（已注册）

#### 指数数据（Index）

- `tool_fetch_index_realtime`（已注册）
- `tool_fetch_index_historical`（已注册）
- `tool_fetch_index_minute`（已注册）
- `tool_fetch_index_opening`（已注册）
- `tool_fetch_global_index_spot`（未纳入当前首发清单）

#### ETF 数据（ETF）

- `tool_fetch_etf_realtime`（已注册）
- `tool_fetch_etf_historical`（已注册）
- `tool_fetch_etf_minute`（已注册）
- `tool_fetch_etf_iopv_snapshot`（已注册）

#### 期权数据（Option）

- `tool_fetch_option_realtime`（已注册）
- `tool_fetch_option_greeks`（已注册）
- `tool_fetch_option_minute`（已注册）

#### 期指/期货（Futures）

- `tool_fetch_a50_data`（已注册）

#### 个股与聚合（Stock）

- `tool_fetch_stock_realtime`（已注册）
- `tool_fetch_stock_historical`（已注册）
- `tool_fetch_stock_minute`（已注册）
- `tool_stock_data_fetcher`（已注册）
- `tool_stock_monitor`（已注册）

#### 财务指标（Financials）

- `tool_fetch_stock_financials`（已注册）

#### 涨停/板块/龙虎榜/资金流/北向

- `tool_fetch_limit_up_stocks`（已注册）
- `tool_sector_heat_score`（已注册）
- `tool_write_limit_up_with_sector`（已注册；是否写入需看缓存策略/配置）
- `tool_limit_up_daily_flow`（已注册；是否写入需看缓存策略/配置）
- `tool_dragon_tiger_list`（已注册）
- `tool_capital_flow`（已注册）
- `tool_fetch_northbound_flow`（已注册）
- `tool_fetch_sector_data`（已注册）

#### 盘前/政策/宏观/公告/行业要闻

- `tool_fetch_policy_news`（已注册）
- `tool_fetch_macro_commodities`（已注册）
- `tool_fetch_overnight_futures_digest`（已注册）
- `tool_conditional_overnight_futures_digest`（已注册）
- `tool_fetch_announcement_digest`（已注册）
- `tool_fetch_industry_news_brief`（未纳入当前首发清单）

#### 交易时段/合约/可交易性工具（Utils）

- `tool_get_option_contracts`（已注册）
- `tool_check_trading_status`（已注册）
- `tool_get_a_share_market_regime`（已注册）
- `tool_filter_a_share_tradability`（已注册）
- `tool_fetch_multiple_etf_realtime`（未纳入当前首发清单）
- `tool_fetch_multiple_index_realtime`（未纳入当前首发清单）
- `tool_fetch_multiple_option_realtime`（未纳入当前首发清单）
- `tool_fetch_multiple_option_greeks`（未纳入当前首发清单）

#### 本地缓存读取（read_*）

- `tool_read_market_data`（已注册）
- `tool_read_index_daily`（已注册）
- `tool_read_index_minute`（已注册）
- `tool_read_etf_daily`（已注册）
- `tool_read_etf_minute`（已注册）
- `tool_read_option_minute`（已注册）
- `tool_read_option_greeks`（已注册）

#### Tick（可选，不纳入首发）

- `fetch_tick_with_quality`（未纳入当前首发清单）

---

### 首发 MVP 工具（建议优先用）

- `tool_fetch_market_data` — 跨资产统一入口（推荐）
- `tool_get_option_contracts` — 根据 underlying 获取期权合约
- 兼容入口：`tool_fetch_index_data`、`tool_fetch_etf_data`、`tool_fetch_option_data`

---

### 缓存策略（重要）

#### 磁盘缓存语义（Disk Parquet）

插件默认设计为：**不开磁盘 parquet 写入**。

在 `config.yaml`：

- `data_cache.enabled: false`（默认）
  - 允许磁盘缓存「读取」（如果已有 parquet 存在）
  - 跳过磁盘缓存「写入」（插件不会创建/覆盖 parquet 文件）
  - 如果缓存 parquet 不可读/损坏，本模式会避免删除坏文件
- `data_cache.enabled: true`
  - 允许磁盘缓存「读 + 写」

#### 通用工具返回契约（建议字段）

大多数 `tool_*` 会返回 JSON 对象，常见字段包括：

- `success`: `true|false`
- `data`: 获取/处理后的数据（失败时可能是 `null`）
- `message`: 可读的状态/错误信息
- `source`: 数据来源（例如 provider 名称或 `cache`）

部分工具还会返回额外字段，如：

- `count`: 记录数/合约数
- `missing_dates`: 缓存中未找到的日期（给 `read_*` 类工具使用）

当可用时，部分工具可能还会提供：

- `timestamp`: 数据时间戳/查询时间（字符串）
- `cache_hit`: 是否命中缓存（`true|false`）
- `cache_hit_detail`: 缓存命中详情（例如命中了哪些日期/分区）

#### Provider fallback 与重试（来自 `config.yaml`）

插件会按 `data_sources.*.priority` 的顺序尝试数据源（例如 `sina -> eastmoney` 等），失败后按以下规则重试：

- 熔断（circuit breaker）：`data_sources.circuit_breaker`
  - `enabled`：是否启用
  - `error_threshold`：连续错误阈值（默认 `3`）
  - `cooldown_seconds`：熔断后冷却时间（默认 `300`）
- 重试（per provider）：例如 `data_sources.etf_minute.eastmoney/sina`
  - `enabled`：是否启用该 provider
  - `max_retries`：最大重试次数
  - `retry_delay`：每次重试的延迟（秒）

---

### 更多资源

- 源码与 Issue：[GitHub — shaoxing-xie/openclaw-data-china-stock](https://github.com/shaoxing-xie/openclaw-data-china-stock)
- ClawHub 插件页：[openclaw-data-china-stock on ClawHub](https://clawhub.ai/plugins/%40shaoxing-xie%2Fopenclaw-data-china-stock)

---

## License

MIT License（开源免费使用）。
