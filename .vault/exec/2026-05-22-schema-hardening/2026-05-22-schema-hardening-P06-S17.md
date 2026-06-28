---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S17'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` `P06.S17`

Tightened the generic loader/fragment regression gate without adding
per-modelo schema behavior.

- Modified: `src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
- Modified: `.vault/plan/2026-05-22-schema-hardening-plan.md`

## Description

The loader directory-mode suite now includes an explicit synthetic collision
test proving a modelo id cannot be declared by both `modelos/<id>.toml` and
`modelos/<id>/manifest.toml`.

The committed-corpus checks now also assert that discovery reports every TOML
fragment path for directory-mode revision sources. This keeps the generic
source inventory aligned with fragmented revisions such as M100 and any future
modelo fragmentation work.

Existing reviewability gates remain active for maximum single-file line count,
maximum TOML fragment line count, maximum TOML row length, stale single-file
siblings, and multi-revision single-file layouts.

## Tests

`uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
passed.

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
passed with 23 tests.
