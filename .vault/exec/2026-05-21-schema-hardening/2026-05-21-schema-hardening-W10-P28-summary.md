---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W10.P28` summary

Completed the Modelo 200 correction-axis warning guard implementation and
regression tests.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W10-P28-S55.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W10-P28-S56.md`

## Description

The validator now covers the audited balance-only correction axes in the
singleton typo-warning sidecar. The mismatch bucket remains treated as
warning-only behavior, with no registry rewrite and no structured metadata
extraction from disputed role suffixes.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
