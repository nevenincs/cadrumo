---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S68'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W13.P34.S68`

Added regression coverage for legal-reference warning boundaries and reviewed
singleton markers.

- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W13-P34-S68.md`

## Description

The old artificial legal-reference warning tests now assert that `art11_4`
versus `dt1` roles and `rdleg` versus current DI internacional roles are not
axis siblings without source policy. The committed-registry singleton marker
test now covers the 13 Modelo 200 roles exposed by removing the broad
legal-reference guard.

## Tests

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`
