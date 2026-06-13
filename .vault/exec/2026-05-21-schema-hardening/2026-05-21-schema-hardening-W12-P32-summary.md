---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W12.P32` summary

Completed the cross-CCAA warning-boundary implementation, tests, and registry
singleton markers.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2011-2022.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2143-2154.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2144-2155.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2233-2246.toml`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W12-P32-S61.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W12-P32-S62.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W12-P32-S64.md`

## Description

The validator no longer relies on broad CCAA token normalization. Current
legitimate cross-CCAA singleton exposures are handled through explicit
registry cardinality policy.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
