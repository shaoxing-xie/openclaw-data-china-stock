# openclaw-data-china-stock

**面向 A 股个人投资者的 OpenClaw / ClawHub 行情与参考数据底座**

这是一个开源、免费的 OpenClaw / ClawHub **代码插件**：为指数、ETF、个股与挂牌期权提供统一 `tool_*` 接口、多数据源优先级与降级、以及默认安全的缓存策略（`data_cache.enabled=false`：允许读已有 Parquet，默认不写盘）。

**一句话**：少在「接口不稳定、格式不统一、缓存难控」上踩坑，把时间留给策略与工程。

---

### 你应该先看哪里（导航）

- **新手**：先看「三分钟上手」→「统一入口 `tool_fetch_market_data`」→「常用 A 股扩展（P0/P1）」  
- **需要完整工具清单**：直接跳到「工具清单（以 manifest 为准）」  
- **需要排障/复现**：看「`provider_preference`」「缓存策略」「Provider fallback 与重试」  

---

### 核心亮点（概览）

- **统一入口**：优先使用 `tool_fetch_market_data`，跨指数 / ETF / 股票 / 期权；股票另支持 `timeshare` / `pre_market` / `market_overview` / `valuation_snapshot` 等扩展 `view`。
- **多源更稳**：AkShare / 新浪 / 东方财富 / 可选 Tushare + 熔断/重试协作，降低单点不可用对 Agent 工作流的影响。
- **缓存可控**：默认关闭磁盘 Parquet **写入**，避免脏数据污染；离线补数/提速时再显式开启 `data_cache.enabled=true`。
- **面向散户的常用能力**：涨停池、龙虎榜、北向资金、板块热度、期权 Greeks、交易状态与合约查询等（以 `config/tools_manifest.json` 注册为准）。
- **返回契约一致**：多数工具返回带 `success` / `data` / `message` / `source` 的 JSON；部分扩展工具还带 `provider` / `fallback_route` / `attempt_counts` 便于排障。

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

**个股当日分时（统一入口扩展 `view`）：**

```yaml
tools:
  - name: tool_fetch_market_data
    params:
      asset_type: stock
      view: timeshare
      asset_code: "600000"
      mode: production
```

**更多能力（示例）**：主数据 `tool_fetch_a_share_universe`、指数成份 `tool_fetch_index_constituents`、涨停池 `tool_fetch_limit_up_stocks`、北向 `tool_fetch_northbound_flow`、龙虎榜 `tool_dragon_tiger_list`（完整列表见下文清单）。

> 提示：本文后半部分有**完整工具清单**与**缓存/降级/重试**策略；建议把它当作“数据层使用手册”。

---

### 安装

**当前发布版本（npm / ClawHub 以 registry 为准）：`0.2.1`**

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

### 常用 A 股扩展（P0 / P1，与统一入口配合）

这一节只回答一个问题：**“除了行情 K 线，我还能用哪些参考数据？”**（以 `config/tools_manifest.json` 为准）

#### P0（底座：主流程离不开）

| 工具 ID | 能力 |
|--------|------|
| `tool_fetch_a_share_universe` | 沪深京 A 股代码/简称主数据 |
| `tool_fetch_stock_financial_reports` | 三大表（报告期） |
| `tool_fetch_stock_corporate_actions` | 分红/解禁/增发/配股/回购 |
| `tool_fetch_margin_trading` | 两融（汇总/明细/标的） |
| `tool_fetch_block_trades` | 大宗交易（统计/明细/排行） |

#### P1（增强：能用更好，但不应阻塞主流程）

| 工具 ID | 能力 | 关键参数（节选） |
|--------|------|------------------|
| `tool_fetch_stock_shareholders` | 十大股东/户数/基金持股等 | `holder_kind`；户数可 `provider_preference=cninfo|ths` |
| `tool_fetch_ipo_calendar` | IPO 申报/上市/辅导/摘要 | `ipo_kind`；部分需 `stock_code` |
| `tool_fetch_index_constituents` | 指数成份（可选权重） | `index_code`；`include_weight`；可 `provider_preference=csindex|sina|eastmoney` |
| `tool_fetch_stock_research_news` | 个股新闻/研报/主新闻流 | `content_kind=news|research|main_feed` |

#### 统一入口在股票上的扩展 `view`

当 `asset_type=stock` 时，除 `realtime` / `historical` / `minute` / `opening` 外，还支持：

| `view` | 含义 | 典型入参 |
|--------|------|-----------|
| `timeshare` | 当日分时（连续竞价时段分钟序列） | `asset_code`（6 位） |
| `pre_market` | 盘前参考/盘前分钟 | `asset_code`；`start_date` / `end_date`（YYYYMMDD） |
| `market_overview` | 两市摘要类总貌（轻量） | `start_date` 可选；`asset_code` 可空 |
| `valuation_snapshot` | 个股估值/主要指标快查 | `asset_code` |

> `minute` 偏 **K 线粒度**；`timeshare` 偏 **当日分时语义**。

#### `provider_preference`（只调整“尝试顺序”）

多源工具支持可选参数 **`provider_preference`**（如 `auto|eastmoney|sina|csindex|cninfo|ths|standard`），与内部降级链并存时仅调整尝试顺序（便于复现与排障）。

---

### Tushare 备份配置

部分数据源会以 Tushare 作为可选兜底：请设置环境变量 `TUSHARE_TOKEN`（或在 `config.yaml` 的 `tushare.token` 中配置）。

> 下面进入完整工具清单（按注册 manifest 展开）。


### 工具分类与接口清单（用于讨论首发暴露范围）

说明：以下 `tool_id` 来自本仓库 `config/tools_manifest.yaml`（运行时以 `config/tools_manifest.json` 注册为准）。
其中「已注册」表示当前版本已在 OpenClaw 中暴露，直接可被工具调用；「未纳入当前首发清单」表示在本仓库代码中可能存在，但尚未纳入当前工具清单（需要后续版本补齐）。

#### 跨资产统一入口（推荐）

- `tool_fetch_market_data`（已注册）
  - `asset_type=index|etf|option|stock`；`view` 含 `realtime|historical|minute|opening|greeks|global_spot|iopv_snapshot`；**股票**另支持 `timeshare|pre_market|market_overview|valuation_snapshot`（`market_overview` 可不填 `asset_code`，可用 `start_date` 作为深交所摘要日期）

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
- `tool_fetch_stock_financial_reports`（已注册，三大表报告期）

#### A 股主数据与公司行为 / 两融 / 大宗

- `tool_fetch_a_share_universe`（已注册）
- `tool_fetch_stock_corporate_actions`（已注册）
- `tool_fetch_margin_trading`（已注册）
- `tool_fetch_block_trades`（已注册）

#### 股东 / IPO / 指数成分 / 新闻研报（P1）

- `tool_fetch_stock_shareholders`（已注册）
- `tool_fetch_ipo_calendar`（已注册）
- `tool_fetch_index_constituents`（已注册）
- `tool_fetch_stock_research_news`（已注册）

多源工具支持可选参数 **`provider_preference`**（如 `auto|eastmoney|sina|csindex|cninfo|ths|standard`），与内部降级链并存时仅调整尝试顺序。

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

- `tool_fetch_market_data` — 跨资产统一入口（推荐）；股票场景善用扩展 `view`（分时/盘前/总貌/估值快照）
- `tool_get_option_contracts` — 根据 underlying 获取期权合约
- **A 股底座**：需要代码表/财报/公司行为/两融/大宗时，直接使用上表 P0 工具；需要股东/IPO/成份/投研资讯时使用 P1 工具
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

A 股扩展类工具（P0/P1、`tool_fetch_market_data` 中部分股票视图）在成功或部分成功时，还可能在 JSON 中附带：

- `provider` / `fallback_route`：实际使用的数据来源或路由链（字符串或列表）
- `attempt_counts`：各上游接口尝试次数（对象），便于 Issue 反馈时说明「哪一段失败」

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

### 测试与质量门禁

- **单元测试（无外网）**：仓库根目录执行  
  `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- **全工具抽检（可选联网）**：  
  `python3 scripts/test_all_tools.py --manifest config/tools_manifest.json --report tool_test_report.json`  
  可加 `--limit N` / `--disable-network`；如需加快可加 `--no-extra-stock-market-views`。
- **L4 列名契约（mock、无网）**：`tests/test_dto_snapshots_l4.py` 与 `tests/fixtures/l4/*.json`
- **报告差异对比**：`python3 scripts/compare_tool_reports.py <baseline.json> <current.json>`（失败数增加则退出码 1；`COMPARE_STRICT=0` 仅打印摘要）
- 详细 Provider 矩阵与扩展能力卡片见 [plugins/data_collection/ROADMAP.md](plugins/data_collection/ROADMAP.md) 附录 F/G。

---

### 免责声明

本插件仅用于**数据采集与技术研究**，不构成任何投资建议或收益承诺。任何使用行为及后果由使用者自行承担。

---

### 更多资源

- 源码与 Issue：[GitHub — shaoxing-xie/openclaw-data-china-stock](https://github.com/shaoxing-xie/openclaw-data-china-stock)
- ClawHub 插件页：[openclaw-data-china-stock on ClawHub](https://clawhub.ai/plugins/%40shaoxing-xie%2Fopenclaw-data-china-stock)

---

## License

MIT License（开源免费使用）。
