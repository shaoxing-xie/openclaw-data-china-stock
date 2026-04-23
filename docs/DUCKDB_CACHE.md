# DuckDB 缓存加速

使用 DuckDB 加速大规模历史数据的聚合和过滤查询。

## 性能提升

Benchmark 结果 (16 线程):

| 数据量 | 聚合查询 | 复杂过滤 + 聚合 |
|--------|----------|-----------------|
| 1 万行 | 4.0x | 3.4x |
| 10 万行 | 2.3x | 3.1x |
| 50 万行 | 2.9x | 4.2x |
| 100 万行 | 3.4x | 5.4x |
| 200 万行 | **7.0x** | **10.1x** |

## 使用方法

```python
from src.duckdb_cache import save_duckdb_cache, aggregate_duckdb_cache

# 保存数据
save_duckdb_cache('index_daily', '000300', df)

# 聚合查询 (2.5-4.8x 加速)
result = aggregate_duckdb_cache(
    'index_daily', '000300',
    aggregations={'close': 'AVG', 'volume': 'SUM'},
    group_by='EXTRACT(YEAR FROM CAST(date AS DATE))'
)
```

## 配置

在 `config.yaml` 中启用/禁用：

```yaml
duckdb_cache:
  enabled: true  # 默认：false
  threads: 16    # 线程数，可调
```

## Benchmark 运行

```bash
python3 benchmarks/benchmark_duckdb_cache.py
```
