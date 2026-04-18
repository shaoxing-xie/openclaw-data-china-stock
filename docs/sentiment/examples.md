# Sentiment Tools Examples

## 1) Limit-up heat

```python
tool_fetch_limit_up_stocks(date="20260418")
```

Key outputs:
- `limit_up_count`
- `prev_limit_up_performance`
- `sentiment_stage`
- `data_quality`

## 2) A-share fund flow (market trend)

```python
tool_fetch_a_share_fund_flow(query_kind="market_history", max_days=20)
```

Key outputs:
- `cumulative.3d/5d/10d`
- `flow_score`
- `attempts`

## 3) Northbound (EOD trend)

```python
tool_fetch_northbound_flow(lookback_days=20)
```

Key outputs:
- `cumulative.5d/20d`
- `statistics.consecutive_days`
- `note` (disclosure-limit reminder)

## 4) Sector strength

```python
tool_fetch_sector_data(sector_type="industry", period="today")
```

Key outputs:
- `source` / `fallback_route` / `as_of`
- `sectors.industry.top_gainers` / `sectors.industry.top_losers`
- `sectors.industry.quality_gate_passed`
- `derived.rotation_speed_score` / `derived.main_line`
- `explanation.main_line_reason` / `explanation.rotation_speed_interpretation`

Sample response (truncated):

```json
{
  "success": true,
  "source": "ths_industry_summary",
  "fallback_route": [],
  "data_quality": "fresh",
  "as_of": "2026-04-18 15:30:00",
  "sectors": {
    "industry": {
      "top_gainers": [
        {
          "sector_name": "半导体",
          "change_percent": 3.2,
          "net_inflow": 12.5
        }
      ],
      "top_losers": [
        {
          "sector_name": "煤炭",
          "change_percent": -1.3,
          "net_inflow": -2.1
        }
      ],
      "total_count": 56,
      "quality_gate_passed": true
    }
  },
  "derived": {
    "rotation_speed_score": 0.4,
    "main_line": "半导体"
  },
  "explanation": {
    "main_line_reason": "主线板块为半导体，基于当期涨跌幅 Top1 识别。",
    "rotation_speed_interpretation": "Top5 相对上一快照重合 3/5，轮动得分 0.4。"
  }
}
```
