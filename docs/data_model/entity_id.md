# `entity_id` 与代码归一（L2）

## 过渡期策略

1. **A 股交易代码**：6 位数字，不带交易所前缀；由 `_norm_code_6` 规则归一（与 `equity_factor_screening`、`reference_p1` 一致）。
2. **指数**：6 位指数码（如 `000300`）；误粘贴超长数字时取前 6 位（与 `reference_p1._norm_index_code` 一致）。
3. **ETF**：上海常见 `51****`、深圳 `15****` / `16****` 等；仍用 6 位作为 `canonical_code`，`entity_type=etf`。
4. **稳定 `entity_id`（可选）**：建议格式 `stk:{code6}`、`idx:{code6}`、`etf:{code6}`，待 `data/master_meta` 补全后强制。

## 解析工具

- `tool_resolve_symbol` / `tool_batch_resolve_symbol`：见 `plugins/data_collection/entity/entity_tools.py`。
