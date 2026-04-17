# Macro Error Codes

| error_code | meaning | action |
|---|---|---|
| `VALIDATION_ERROR` | request arguments invalid | fix dataset/parameter names |
| `UPSTREAM_TIMEOUT` | upstream data source timed out | retry later, reduce scope |
| `UPSTREAM_FETCH_FAILED` | upstream call failed after retries | inspect network and AKShare availability |
| `RUNTIME_ERROR` | unexpected internal error | inspect traceback, raise issue |

All errors should preserve a structured payload under `error`.

