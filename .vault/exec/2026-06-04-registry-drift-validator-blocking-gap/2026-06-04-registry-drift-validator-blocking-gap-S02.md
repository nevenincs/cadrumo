---
tags:
  - '#exec'
  - '#registry-drift-validator-blocking-gap'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S02'
related:
  - '[[2026-06-04-registry-drift-validator-blocking-gap-plan]]'
---

# S02 Typo-Twin Warning Gap Regression

Scope: add a focused regression that proves the selected drift gap is not currently blocked.

## Description

- Added a full-schema `ModeloDefinition` helper for semantic-role validator tests.
- Added a focused typo-twin regression that routes synthetic schema objects through `validate_registry_scope`.
- Proved the current behavior emits a warning for `taxpayer_niff` but returns no validation failure.

## Outcome

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_semantic_role.py` passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_semantic_role.py -q` passed: 37 passed.

## Notes

- This step intentionally documents the current non-blocking behavior; S03 flips this regression to the blocking behavior selected by S01.
