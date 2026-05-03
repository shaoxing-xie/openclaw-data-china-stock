# Data Source Connectors Cross-Table

**Status**: **P0-surface baseline delivered** — §4.1.1 首批业务行 + §4.1.2 双轨矩阵**初版**已落盘；**Future rows** / §3 `schema_link` 为**增量闭合项**（对标规划 **A 档 / B 档**：A=可对账可评审，B=全行冻结 + registry 互链）。本文件是 **cross-table of record**；新增/变更外部分支须同步改表。对账范围：

- **Business semantics** (what consumers need) → **primary `tool_id`** → **`capability_id` (planned)** → **Router `source_id` priority** → **implementation entrypoints**.

It complements (does not replace):

- [`DATA_SOURCE_TOOL_INVENTORY.md`](./DATA_SOURCE_TOOL_INVENTORY.md) — per-tool `expected_source_ids` (inventory / normalization target).
- [`DATA_SOURCE_REGISTRY.md`](./DATA_SOURCE_REGISTRY.md) — canonical `source_id` set and alias rules.

**Governance**: Any new external branch or merged capability row MUST add/update a row here and link back to INVENTORY + REGISTRY.

---

## 1) Business semantic → tool → capability (§4.1.1 baseline)

| business_semantic_id | description | primary_tool_id | planned_capability_id (Router key) | typical_source_id_chain (priority order; see config) | primary_code_paths |
| --- | --- | --- | --- | --- | --- |
| `cn_index.snapshot` | Major CN index latest / historical / minute / opening | `tool_fetch_index_data` | `market.index.multi_view` | `tushare,akshare,sina,eastmoney,mootdx,cache` (+ global merge) | `plugins/merged/fetch_index_data.py`, `plugins/data_collection/index/fetch_*.py` |
| `cn_index.global_spot` | Global index latest snapshot (multi-vendor merge) | `tool_fetch_index_data` (`data_type=global_spot`) | `market.index.global_spot` | `fmp,yfinance,sina,akshare` (policy in `fetch_global.py`) | `plugins/data_collection/index/fetch_global.py` |
| `cn_etf.multi` | ETF OHLC / realtime / minute + IOPV-related tools | `tool_fetch_etf_data`, `tool_fetch_etf_iopv_snapshot` | `market.etf.multi_view` | `tushare,akshare,sina,eastmoney,ths,mootdx,cache` | `plugins/merged/fetch_etf_data.py`, `plugins/data_collection/etf/fetch_*.py` |
| `cn_option.multi` | Option realtime / greeks / minute | `tool_fetch_option_data` | `market.option.multi_view` | `sina,akshare,eastmoney,cache` | `plugins/merged/fetch_option_data.py`, `plugins/data_collection/option/fetch_*.py` |
| `futures.a50` | A50 and related futures spot/hist | `tool_fetch_a50_data` | `market.futures.a50` | `eastmoney,akshare,sina,cache` | `plugins/data_collection/futures/fetch_a50.py` |
| `cn_stock.multi` | A-share stock hist / minute / realtime | `tool_fetch_stock_historical`, `tool_fetch_stock_minute`, `tool_fetch_stock_realtime`, `tool_stock_data_fetcher` | `market.stock.multi_view` | `tushare,akshare,sina,eastmoney,mootdx,baostock,efinance,cache` | `plugins/data_collection/stock/fetch_*.py` |
| `cn_limit_up.pipeline` | Limit-up pool + quality gate | `tool_fetch_limit_up_stocks` | `sentiment.limit_up.pool` | `akshare,eastmoney,cache` | `plugins/data_collection/limit_up/fetch_limit_up.py` |
| `cn_sector.board` | Sector / industry board snapshot | `tool_fetch_sector_data` | `market.sector.board` | `ths,sina,eastmoney,akshare,cache` | `plugins/data_collection/sector.py` |
| `cache.read.market` | Read cached parquet views (no silent online refill in plugin path) | `tool_read_market_data` (+ aliases) | `cache.market.read` | `cache` | `plugins/merged/read_market_data.py`, `plugins/data_access/read_cache_data.py` |

**Notes**

- `expected_source_ids` in INVENTORY uses shorthand buckets (`derived`, etc.). Rows here spell **orchestration vs `source_stage`**; see §2 and project plan §4.2.13–4.2.14.
- **Router priority** authoritative runtime copy: `config.yaml` / assistant `config/domains/market_data.yaml` — this table is the **documentation mirror** to be kept in sync during P1.
- **Tushare（§5.1 T1）**：**表一**（日线 / `moneyflow` / `moneyflow_hsgt` / 期权日行情等 Pro 接口）与 **表二**（`stk_mins`、分钟级 `pro_bar` 等）权限分离；默认 `permission_profile: "2000"` **不**等同于表二已购。表二启用条件：`tushare.permission_profile: "minute_table2"` 或 `tushare.minute_table2: true` 或测试环境 `TUSHARE_FORCE_STK_MINS=1`；门闸实现见 `plugins/connectors/tushare/__init__.py::is_stk_mins_entitled` 与助手 `src/tushare_stk_mins_entitlement.py`。

---

## 2) Dual-track metadata matrix (§4.1.2 / §4.2.14 task N — initial rows)

**Tracks**

- **Meta-A (`with_source_meta`)**: `source`, `source_id` (`canonical_source_id`), `source_raw`, `source_stage`, `source_interface`, optional `source_vendor`.
- **Meta-B (`normalize_contract` + sentiment contract)**: `used_fallback`, `fallback_route`, `error_code`, `error_message`, `attempts` (shape may differ per tool), `quality_status` / `data_quality` where applicable.

| tool_id | Meta-A present (typical) | Meta-B present | L4 consumer MUST read (minimum) | implementation_notes |
| --- | --- | --- | --- | --- |
| `tool_fetch_index_data` (non-`global_spot`) | Yes when sub-route wraps `with_source_meta` | Usually partial | `success`, `source`/`source_id` when present, `message` on failure | Merged router; per-`data_type` delegates to `fetch_*` |
| `tool_fetch_index_data` (`data_type=global_spot`) | **Yes** (`source_stage=derived` on multi-source success) | **Yes** (`attempts`) | **`source_stage` + `attempts` (+ `sources_used`)**; do not judge by `source_id` alone | `mixed` / composite `source_raw` may yield `source_id=unknown` via `canonical_source_id` |
| `tool_fetch_limit_up_stocks` | Via normalized payload / `source` string | **Yes** (`normalize_contract`) | `success`, `error_code`, `attempts`, `quality_gate` | Quality gate failures use `UPSTREAM_FETCH_FAILED` |
| `tool_read_market_data` | N/A (cache read via `read_cache_data`) | **Yes** (`error_code`, `_meta.quality_status` on failures; multi-type partial → `degraded`) | `success`, `error_code`, `_meta.quality_status`, `missing_dates` / records | 插件 `plugins/merged/read_market_data.py` 已与助手对齐契约字段 |

**Future rows**: extend the same table for `tool_fetch_etf_data`, `tool_fetch_a50_data`, northbound, fund flow, stock minute, etc., during P1 connector migration.

**P3 note (`tool_fetch_limit_up_stocks`)**: AkShare approved 链（em → previous → strong → sub_new）在相邻调用间执行 `plugins.utils.upstream_spacing.sleep_limit_up_between_pools`，间隔来自 `data_sources.limit_up.upstream_chain_spacing_seconds`（或 `intraday_tool_spacing_seconds` / 环境变量 `OPENCLAW_LIMIT_UP_CHAIN_SPACING_SECONDS`）。

---

## 3) Schema / task map links (placeholders)

Unified data layer registry paths live primarily in the **assistant** repo (`etf-options-ai-assistant`) per project rules. When a connector row stabilizes, add pointers:

- `schema_registry.yaml` — dataset name, `schema_version`, L2/L4 layer.
- `task_data_map.yaml` — `task_id` ↔ producer tool / cron.

Until linked, mark `schema_link: TODO` in future extended rows (optional column in a later revision).

---

## 5) L4 最低必填字段组草案（§4.1.6 任务 S）

| semantic view / 消费方 | 最低字段（成功帧） | schema_link |
| --- | --- | --- |
| Chart global snapshot | `success`, `sources_used` 或等价、`quality_status` | 见助手 `data/semantic/global_market_snapshot/` |
| 指数 tool 帧 | `success`, `data`, `message`, `source_id` 或 `attempts` | `schema_registry.yaml` TODO 行 |
| 只读 cache 工具 | `success`, `data.records` 或 `missing_dates` | 任务 S：与 `task_data_map` 对齐后补链 |

---

## 6) 跨进程对照检查项（§4.1.6 任务 T）

| 检查项 | Gateway（插件 tool_runner） | 助手同参 import |
| --- | --- | --- |
| `tool_read_market_data` 日线默认窗 + `since` | 调用 `tool_read_market_data` JSON | `plugins/merged/read_market_data.py` |
| `tool_read_market_data` 分钟 `date`-only | 同上 | 与插件 `plugins/merged/read_market_data.py` 已对齐拷贝 |
| `read_cache_data` 在线补拉默认关闭 | 返回体无隐式全量补拉副作用 | `skip_online_refill` 默认 `True`（助手） |
| `tool_run_data_cache_job` | 独立插件 venv 跑 intraday 链 | `src/data_cache_collection_core.py` 已纳入插件 `src/` |

---

## 7) `unknown` 率与 `source_raw` TopN（§4.2.14 任务 O — 模板）

在日志或 L3 聚合管道中按日统计：

- `count_unknown = sum(source_id == 'unknown')`
- `top_source_raw = TopN(source_raw where source_id unknown)`

告警阈值由运维在观测系统中配置；字段名与 **§4.1.2** 双轨一致。

---

## 8) 额外工具矩阵行（P0 扩展）

| tool_id | Meta-A | Meta-B | L4 consumer MUST read | implementation_notes |
| --- | --- | --- | --- | --- |
| `tool_fetch_etf_data` | 部分路由 | 部分 | `success`, `quality_status`, `message` | P1 connector 迁移中补全 |
| `tool_fetch_a50_data` | 是 | 部分 | `success`, `hist_data` / `spot` 块 | 见 `futures/fetch_a50.py` 头注释（fallback 占位技术债） |
| `tool_probe_source_health` | N/A | N/A | 仅运维只读 JSON | `data/meta/source_health_snapshot.json` |

---

## 10) Failure response contract (`error_code`)

Canonical enum strings live in **`plugins/utils/error_codes.py`** (`ErrorCode` / `QualityStatus`). Assistant SSOT for human-readable descriptions: **`data/meta/error_codes.yaml`** (etf-options-ai-assistant).

| Field | When present | Notes |
| --- | --- | --- |
| `success` | Always | `false` on hard tool failure |
| `error_code` | On failure | One of `UPSTREAM_FETCH_FAILED`, `RATE_LIMITED`, `INVALID_PARAMS`, `NO_DATA`, `PLUGIN_UNAVAILABLE`, `CACHE_MISS` |
| `quality_status` | Recommended | `ok` / `degraded` / `error` (see YAML `quality_status.enum`) |
| `_meta.error_code` | Optional | Mirror top-level for L4 readers |
| `message` | Optional | Human text; must not replace `error_code` |

**`tool_read_market_data`**: invalid args → `INVALID_PARAMS`; cache partial / cache miss paths → `CACHE_MISS` (may carry `quality_status=degraded`); empty or unknown failure → `NO_DATA`; upstream/read failure with message → `UPSTREAM_FETCH_FAILED`. Multi-type partial success → `quality_status=degraded`, `error_code=UPSTREAM_FETCH_FAILED`.

**`tool_probe_source_health`**: per-row import failure → row `error_code=PLUGIN_UNAVAILABLE` (with `ok=false`); snapshot persistence exception → top-level `success=false`, `error_code=UPSTREAM_FETCH_FAILED`, `_meta.quality_status=error`. Dry-run / successful snapshot → `success=true` (rows may still carry `error_code` on failed probes).

---

## 9) Changelog

- **2026-05-02**: Initial文件（P0-surface Q+R）：业务映射 + 双轨矩阵种子。
- **2026-05-02**：§5–§8 增补（S/T 草案、`unknown` 模板、矩阵行、A50 技术债指针）。
- **2026-05-03**：§10 失败体 `error_code` 契约 + `tool_read_market_data` / `tool_probe_source_health` 说明。
