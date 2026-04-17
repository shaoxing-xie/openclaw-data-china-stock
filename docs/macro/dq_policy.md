# Macro Data Quality Policy

## Freshness

- Warn threshold: `staleness_days > 45`
- Error threshold: `staleness_days > 120`

## Completeness

For snapshot and narrative generation, these core datasets are mandatory:

- growth: `pmi_official`
- inflation: `cpi` (or `ppi`)
- credit: `social_financing`

If any is missing, return `insufficient_evidence`.

## Traceability

Each response should expose:

- `source`
- `as_of`
- `release_time` (when available)
- `revision_policy`

