---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S06'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
---



# `schema-hardening` `P02.S06`

Added end-to-end real-behavior tests for schema, loader, advisory reporting,
and opt-in strict hard failure.

- Modified: `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p02-s06-review.md`

## Description

Added TOML-backed directory-mode tests that load a modelo through the real
registry loader and schema validation before exercising continuity behavior.
The advisory case verifies continuity/evolution metadata appears in the drift
inventory and does not fail registry-scope validation. The strict case verifies
an uncovered non-overlapping label drift fails through registry-scope
validation.

These tests complement the unit-level schema, fragment-loader, advisory, and
strict checks landed in the previous plan steps.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

The pytest run passed with four existing singleton semantic-role warnings for
M347 emitted by committed-corpus registry validation.
