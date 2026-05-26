---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
step_id: 'S17'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
