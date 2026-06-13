---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S56'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W10.P28.S56`

Added regression tests for the Modelo 200 correction-axis warning-sidecar
hardening.

- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W10-P28-S56.md`

## Description

The new tests prove that balance-only `saldo_inicial` and `saldo_final`
correction roles no longer emit typo warnings. They also document that a known
mismatch-bucket base remains warning-only: the typo-warning validator may keep
the pair quiet, but this does not authorize registry metadata extraction from
the disputed suffix.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
