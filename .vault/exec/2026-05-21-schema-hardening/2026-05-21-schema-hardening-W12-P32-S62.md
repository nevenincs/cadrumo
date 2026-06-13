---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S62'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W12.P32.S62`

Added regression coverage for the cross-CCAA warning boundary and reviewed
singleton markers.

- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W12-P32-S62.md`

## Description

The old artificial CCAA-axis test now asserts that cross-CCAA role names are
not axis siblings without source policy. The committed-registry singleton
marker test now includes the four Modelo 100 roles exposed by removing the
broad CCAA guard.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
