"""
DuckDB 缓存加速 Benchmark

测试场景：
1. 聚合查询 (GROUP BY + AVG/SUM)
2. 复杂过滤 + 聚合

对比：
- pandas: 全量加载 parquet -> 内存过滤/聚合
- DuckDB: 直接查询 parquet，利用谓词下推和计算下推
"""

import pandas as pd
import duckdb
import time
from pathlib import Path
import numpy as np
from datetime import datetime, timedelta

TEST_ROWS = [10000, 100000, 500000, 1000000, 2000000]
CACHE_DIR = Path("./benchmark_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def generate_test_data(n_rows: int) -> pd.DataFrame:
    """生成模拟指数日线数据"""
    print(f"生成 {n_rows:,} 行测试数据...")

    # 生成日期序列
    all_dates = pd.date_range(start='2020-01-01', end='2026-04-06', freq='B')
    if len(all_dates) < n_rows:
        dates = pd.DatetimeIndex(list(all_dates) * ((n_rows // len(all_dates)) + 1))[:n_rows]
    else:
        dates = all_dates[:n_rows]

    # 生成价格数据
    base_price = 3500
    returns = np.random.normal(0.0003, 0.015, len(dates))
    close = base_price * np.cumprod(1 + returns)
    open_ = close * (1 + np.random.uniform(-0.008, 0.008, len(dates)))
    high = np.maximum(open_, close) * (1 + np.random.uniform(0, 0.015, len(dates)))
    low = np.minimum(open_, close) * (1 - np.random.uniform(0, 0.015, len(dates)))
    volume = np.random.uniform(1e8, 5e9, len(dates))

    return pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'open': open_.round(2), 'high': high.round(2), 'low': low.round(2),
        'close': close.round(2), 'volume': volume.round(0).astype(int),
        'amount': (volume * close).round(2)
    })


def benchmark_pandas(parquet_path: Path, n_iter: int = 10) -> dict:
    """Benchmark pandas 方案"""
    results = {}

    # 聚合查询
    times = []
    for _ in range(n_iter):
        start = time.perf_counter()
        df = pd.read_parquet(parquet_path)
        df['year'] = pd.DatetimeIndex(df['date']).year
        result = df.groupby('year').agg({'close': 'mean', 'volume': 'sum'}).reset_index()
        times.append(time.perf_counter() - start)
    results['aggregation'] = np.mean(times) * 1000

    # 复杂过滤 + 聚合
    times = []
    for _ in range(n_iter):
        start = time.perf_counter()
        df = pd.read_parquet(parquet_path)
        df = df[(df['close'] > 3800) & (df['volume'] > 2e9)]
        result = df.groupby(df['date'].str[:4]).agg({'close': 'mean'}).reset_index()
        times.append(time.perf_counter() - start)
    results['complex'] = np.mean(times) * 1000

    return results


def benchmark_duckdb(parquet_path: Path, n_iter: int = 10) -> dict:
    """Benchmark DuckDB 方案"""
    results = {}

    # 聚合查询
    times = []
    for _ in range(n_iter):
        start = time.perf_counter()
        result = duckdb.query(f"""
            SELECT EXTRACT(YEAR FROM CAST(date AS DATE)) AS year,
                   AVG(close) AS avg_close, SUM(volume) AS sum_volume
            FROM '{parquet_path}'
            GROUP BY year
        """).df()
        times.append(time.perf_counter() - start)
    results['aggregation'] = np.mean(times) * 1000

    # 复杂过滤 + 聚合
    times = []
    for _ in range(n_iter):
        start = time.perf_counter()
        result = duckdb.query(f"""
            SELECT SUBSTRING(date, 1, 4) AS year, AVG(close) AS avg_close
            FROM '{parquet_path}'
            WHERE close > 3800 AND volume > 2000000000
            GROUP BY year
        """).df()
        times.append(time.perf_counter() - start)
    results['complex'] = np.mean(times) * 1000

    return results


def run_benchmark():
    print("=" * 60)
    print("DuckDB 缓存加速 Benchmark")
    print("=" * 60)

    for n_rows in TEST_ROWS:
        print(f"\n--- {n_rows:,} 行数据 ---")

        # 生成数据
        df = generate_test_data(n_rows)
        parquet_path = CACHE_DIR / f"data_{n_rows}.parquet"
        df.to_parquet(parquet_path, index=False, compression='snappy')
        print(f"Parquet 大小：{parquet_path.stat().st_size / (1024 * 1024):.1f} MB")

        # 测试
        pandas_res = benchmark_pandas(parquet_path)
        duckdb_res = benchmark_duckdb(parquet_path)

        # 打印结果
        print(f"\n{'查询类型':<15} {'Pandas (ms)':<12} {'DuckDB (ms)':<12} {'加速比':<8}")
        print("-" * 47)
        for op in ['aggregation', 'complex']:
            p_ms, d_ms = pandas_res[op], duckdb_res[op]
            speedup = p_ms / d_ms if d_ms > 0 else 0
            name = '聚合查询' if op == 'aggregation' else '复杂过滤 + 聚合'
            print(f"{name:<15} {p_ms:>10.1f}     {d_ms:>10.1f}     {speedup:>6.2f}x")


if __name__ == "__main__":
    run_benchmark()
