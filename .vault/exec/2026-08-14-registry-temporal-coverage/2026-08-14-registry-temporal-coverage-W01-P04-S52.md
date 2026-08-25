---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:0126072f91370d0da2f4dcc9387d8d8833f1ffc394417a5bbfe4abcc7f5f96d9'
step_id: 'S52'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Decompose the three validators that exceed the reviewability ratchet, _validate.py, _validate_cross_revision.py, and _validate_revision_rules.py, into existing family-owned validation modules or new single-responsibility family modules without raising baselines, duplicating dispatch, or changing validation order and refusal facts, and prove the reviewability plus full validator gates

## Scope

- `src/cadrumo/domain/calculations/registry/_validate.py`
- `src/cadrumo/domain/calculations/registry/_validate_cross_revision.py`
- `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py`
- `src/cadrumo/domain/calculations/registry/tests/test_registry_reviewability.py`

## Description

- Located the existing validation-family ownership and retained the current registry and per-revision dispatchers unchanged.
- Extracted producer-inventory closure checks from `_validate.py` into a single-responsibility accumulating helper.
- Extracted continuity-evolution and retirement-integrity checks from `_validate_cross_revision.py`, retaining its strict-drift wrapper and compatibility imports.
- Extracted dated-value and bracket temporal-coverage checks from `_validate_revision_rules.py`, retaining the existing caller names and diagnostic order.
- Kept every parent and new helper below the live reviewability ceilings without changing a baseline.

## Outcome

- Commit `4b1e1e4e58` reduces the three parent modules to 294, 242, and 283 lines; the extracted helpers are 42, 225, and 157 lines.
- The focused behavioral validator suite passed with 98 tests and 4 deselections.
- The reviewability, closure, and public-boundary suite passed with 13 tests.
- Ruff lint, Ruff formatting, and scoped diff checks passed.

## Notes

- No public export, dispatcher count, validation ordering, refusal diagnostic, or reviewability baseline changed.
