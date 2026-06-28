---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S61'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W12.P32.S61`

Removed broad autonomous-community token sibling recognition from the
semantic-role typo-warning validator.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W12-P32-S61.md`

## Description

The validator no longer treats CCAA tokens as a generic warning-only axis.
Source-approved family-local guards remain in place, but cross-region role
similarity now requires explicit source-backed policy or singleton marking.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
