---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S05'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
---



# `schema-hardening` `P02.S05`

Wired opt-in strict continuity validation into registry-scope validation.

- Modified: `src/aeat/domain/calculations/registry/_validate_cross_revision.py`
- Modified: `src/aeat/domain/calculations/registry/_validate_registry_scope.py`
- Modified: `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p02-s05-review.md`

## Description

Added strict continuity failure generation for non-overlapping revision pairs
when either revision declares `continuidad_validation = "strict"`. Uncovered
field drift now fails registry-scope validation; drift covered by an explicit
matching evolution declaration passes. Advisory revisions keep the prior
inventory-only behavior.

Added real registry-scope tests for advisory drift, strict uncovered drift, and
strict drift covered by `label_evolved`.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/_validate_registry_scope.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

The pytest run passed with four existing singleton semantic-role warnings for
M347 emitted by committed-corpus registry validation.
