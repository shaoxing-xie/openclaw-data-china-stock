# Sentiment Error Codes

| error_code | meaning | action |
|---|---|---|
| `VALIDATION_ERROR` | invalid request argument | fix request parameters |
| `UPSTREAM_FETCH_FAILED` | all sources failed or quality gate rejected | retry later / inspect attempts |
| `UPSTREAM_TIMEOUT` | upstream timeout exceeded | use lower scope or rely on cache |
| `RUNTIME_ERROR` | unexpected internal error | inspect traceback and open issue |
