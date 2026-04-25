# Market Source 24h Regression

## Planned Soak Command
- `python scripts/smoke_market_sources.py --mode soak --duration-hours 24 --interval-seconds 300 --output /tmp/market_soak_24h.json`
- `python scripts/smoke_market_sources.py --summarize /tmp/market_soak_24h.json`

## Metrics To Track
- `elapsed_p95_ms`
- `a50_cache_hit_ratio`
- `empty_value_ratio_avg`
- failure distribution from each run's `global.success` / `a50.first_success` / `a50.second_success`

## Gate
- `global_spot p95 < 3000ms` (in-network environments with configured keys)
- hot-path A50 second call keeps high `cache_hit_ratio`
- no silent degradation: `quality=degraded` must include `degraded_reason`
