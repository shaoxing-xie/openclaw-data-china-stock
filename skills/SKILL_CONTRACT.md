# Skill Contract (openclaw-data-china-stock)

This document defines the shared contract for all skill assets in this repository.

## Directory layout

Each skill must follow:

- `skills/<skill-name>/SKILL.md`
- `skills/<skill-name>/README.md`
- `skills/<skill-name>/config/<skill-name>_config.yaml`
- `skills/<skill-name>/references/*.md`

## Required frontmatter fields

All `SKILL.md` files must include:

- `name`
- `description`
- `version`
- `author`
- `tags`
- `triggers`

## Required sections

All `SKILL.md` files must include:

- `## 目标`
- `## 输入`
- `## 输出（固定结构）`
- `## 强制规则`
- `## 依赖工具`
- `## 通用输出字段`

## Shared safety rules

- Data first, interpretation second.
- No direct execution instructions (position, leverage, buy/sell timing).
- If core evidence is missing, output `insufficient_evidence`.
- Explain key risk counterevidence and confidence band.
- Thresholds/policies must be read from per-skill config files, not hardcoded in narrative.

