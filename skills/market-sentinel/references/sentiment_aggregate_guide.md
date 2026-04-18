# 情绪聚合说明（market-sentinel）

- 四工具并行拉取后做证据归一，再按 `market-sentinel_config.yaml` 的权重与 `risk_mode` 计算综合分。
- `sentiment_stage` 含冰点、修复、高潮、退潮、震荡、混沌；阈值以配置文件为准，不在此重复具体数值。
- 任一子源失败时：重标化可用项权重，填写 `risk_counterevidence` 与 `data_completeness_ratio`，仍使用统一输出模板。
