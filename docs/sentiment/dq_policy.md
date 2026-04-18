# Sentiment Data Quality Policy

## Quality gate checks

- **Structure**: required fields present.
- **Scale**: minimum record threshold by object type.
- **Null ratio**: reject if null ratio exceeds configured threshold.

## Thresholds (initial)

- `limit_up_pool`: min 5 records on single-day query
- `sector_snapshot_industry`: min 30 records
- `sector_snapshot_concept`: min 10 records
- `fund_flow_rank`: min 1 record, null ratio <= 0.85

## Quality labels

- `fresh`: upstream passed gate
- `cached`: returned from local TTL cache
- `partial`: returned with reduced confidence or failed gate fallback
