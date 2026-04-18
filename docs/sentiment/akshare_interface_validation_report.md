# AKShare Interface Validation Report (Manual + Scripted)

This document is generated/maintained from:
- `scripts/sentiment/run_akshare_interface_validation.py`
- `docs/sentiment/reports/akshare_interface_validation_latest.md`

## Scope

- Focus on first-wave 6 interfaces used by four sentiment tools.
- Validation dimensions:
  - availability (`ok`)
  - latency (`elapsed_ms`)
  - shape stability (`columns_sample`)
  - minimum records (`record_count`)

## Latest run

Run command:

```bash
python3 scripts/sentiment/run_akshare_interface_validation.py
```

Artifacts:
- `docs/sentiment/reports/akshare_interface_validation_latest.json`
- `docs/sentiment/reports/akshare_interface_validation_latest.md`

## Optional dependency note

- `akshare-proxy-patch` is supported as an **optional** enhancement, not a required dependency.
- Install only when needed:

```bash
python -m pip install -r requirements-optional.txt
```

- In this project, the primary stability baseline remains:
  - bypass proxy environment for Eastmoney-sensitive AKShare calls (`without_proxy_env`)
  - fallback chain + quality gate + cache

## Classification policy

- `production_ready`: success and quality gate passed.
- `fallback_only`: callable but unstable in record count/latency.
- `temporarily_unavailable`: repeated errors or malformed payload.

## Decision gate

- This report provides evidence only.
- Final primary/secondary call order is reviewed with user before marked approved.
