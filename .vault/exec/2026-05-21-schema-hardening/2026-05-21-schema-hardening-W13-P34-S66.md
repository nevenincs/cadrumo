---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S66'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W13.P34.S66`

Removed broad legal-reference token sibling recognition from semantic-role
typo-warning axis handling.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W13-P34-S66.md`

## Description

The validator no longer strips legal-reference tokens such as `art*`, `dt*`,
`rdleg`, or `lis` before comparing singleton semantic roles for typo-warning
suppression. Legal-reference markers now remain part of the preserved role
stem unless a later source-backed exact-family policy explicitly authorizes a
narrower warning-sidecar rule.

## Tests

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`
