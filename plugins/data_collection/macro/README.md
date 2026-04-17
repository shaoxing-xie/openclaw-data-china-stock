# Macro Data Tools

This module provides China macro collection tools for OpenClaw.

## Primary tools

- `tool_fetch_macro_data`: unified macro entry with `dataset`.
- `tool_fetch_macro_snapshot`: growth/inflation/credit snapshot for strategy narration.

## Compatibility tools

The `tool_fetch_macro_*` functions are compatibility wrappers that route to
`tool_fetch_macro_data`.

## Return contract

All macro tools return the same top-level fields:

- `success`
- `data`
- `source`
- `unit`
- `as_of`
- `data_lag_days`
- `staleness_days`
- `warnings`
- `error`

When upstream fetch fails, `error.error_code` is one of:

- `UPSTREAM_TIMEOUT`
- `UPSTREAM_FETCH_FAILED`
- `VALIDATION_ERROR`

