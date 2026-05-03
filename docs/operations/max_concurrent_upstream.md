# maxConcurrentUpstream 与源链 burst

- 插件 `openclaw.plugin.json` → `maxConcurrentUpstream`：进程内上游 HTTP/AkShare **并发上限**（0 表示不限制）。
- 与 `config/factor_registry.yaml` 中 `source_chains` **协同**：catalog 未来可标注「串行段」；当前以代码内节流（如 `upstream_spacing`）为准。`fetch_global_index_spot` 已将 catalog 与 `data_sources.global_index.latest.priority` **合并**（见 `docs/data_model/catalog_runtime_alignment.md`），`source_route.catalog_merge` 可观测。
- 变更并发默认值时，需回归 `tests/test_fetch_global_source_policy.py` 等与节流相关的用例。
