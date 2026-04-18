# Sentiment Tools API Contract

Applies to:
- `tool_fetch_limit_up_stocks`
- `tool_fetch_a_share_fund_flow`
- `tool_fetch_northbound_flow`
- `tool_fetch_sector_data`

## Unified top-level fields

- `success`: bool
- `source`: winner data source
- `fallback_route`: attempted sources in order
- `used_fallback`: whether winner is not first source
- `attempts`: source-level attempt records
- `as_of`: generation timestamp
- `data_quality`: `fresh | cached | partial`
- `cache_hit`: bool
- `error_code`: nullable, e.g. `UPSTREAM_FETCH_FAILED`
- `error_message`: nullable
- `explanation`: short human-readable explanation

## Backward compatibility

Existing business fields are preserved (e.g. `data`, `records`, `leaders`, `signal`).

## Example (abbreviated)

```json
{
  "success": true,
  "source": "akshare.stock_zt_pool_em",
  "fallback_route": ["akshare.stock_zt_pool_em"],
  "used_fallback": false,
  "attempts": [{"source":"akshare.stock_zt_pool_em","ok":true,"message":"20260418"}],
  "as_of": "2026-04-18 11:00:00",
  "data_quality": "fresh",
  "cache_hit": false,
  "error_code": null,
  "error_message": null,
  "explanation": "..."
}
```
