---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S64'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W12.P32.S64`

Marked four source-grounded Modelo 100 cross-CCAA warning exposures as
intentional singletons.

- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2011-2022.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2143-2154.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2144-2155.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2233-2246.toml`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W12-P32-S64.md`

## Description

The four registry rows exposed by removing the broad CCAA guard are now
explicit `intentional_singleton` roles with source-backed reasons. This keeps
the warning-count gate clean without reinstating cross-CCAA normalization.

## Tests

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
