# Market Source Before/After

## Experiment
- Command:
  - `python scripts/smoke_market_sources.py --mode before --output /tmp/market_before.json`
  - `python scripts/smoke_market_sources.py --mode after --output /tmp/market_after.json`
  - `python scripts/smoke_market_sources.py --compare /tmp/market_before.json /tmp/market_after.json`

## Result Snapshot
- before elapsed: `48318ms`
- after elapsed: `43933ms`
- delta: `-4385ms`
- before empty ratio: `0.0`
- after empty ratio: `0.0`
- before a50 cache hit(second call): `true`
- after a50 cache hit(second call): `true`

## Notes
- FMP key is not configured in this environment, so global route was effectively `yfinance -> sina`.
- A50 second call hit cache (`cache_hit=true`) with `cache_age_ms=0`, matching short-TTL warm-path expectation.

## 最终验收结论（5轮分位数）

在固定前提 `set -a; source /home/xie/.openclaw/.env; set +a` 下完成 5 轮测试，结果表明：

- 正确性稳定达标：`global_success_ratio=1.0`，`global_empty_ratio_avg=0.0`
- `global` 阶段耗时稳定：`p50=595ms`，`p95=1021ms`，`max=1021ms`
- `index_futures` 冷启动（A50首次实时链路）存在外部源波动：`p50=29855ms`，`p95=36591ms`，`max=36591ms`
- `index_futures` 热路径（A50缓存命中）近似瞬时：`p50=0ms`，`p95=0ms`，`max=0ms`
- A50 缓存命中稳定：`a50_source_stage_hit_ratio=1.0`（`source_stage=cache`）

综合判断：**正确性已达标，A50缓存命中稳定；性能受外部源波动影响，应以分位数持续观测，重点关注 index_futures 冷启动阶段。**

### 备注

- `index_futures` 热路径统计出现 `0ms`，是整数毫秒口径下的舍入结果，表示缓存命中后返回极快。
