---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S55'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W10.P28.S55`

Implemented the audited Modelo 200 correction-axis warning-sidecar balance
guard.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W10-P28-S55.md`

## Description

The semantic-role typo-warning validator now treats `saldo_inicial` and
`saldo_final` as correction-table warning axes when two roles preserve the
same base stem. This is warning-only behavior and does not rewrite registry
roles or extract correction metadata.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
