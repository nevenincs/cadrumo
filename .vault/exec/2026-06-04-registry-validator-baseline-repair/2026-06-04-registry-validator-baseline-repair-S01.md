---
tags:
  - '#exec'
  - '#registry-validator-baseline-repair'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S01'
related:
  - '[[2026-06-04-registry-validator-baseline-repair-plan]]'
---

# `registry-validator-baseline-repair` `S01` repair

Scope: compress `_validate_relation_periods.py` docstrings without changing
validator semantics.

## Description

- Replaced verbose dirty docstring additions with compact one-line docstrings.
- Preserved the documentation intent about relation selectors, revision
  coverage, and observation-history coverage.
- Left validator logic untouched.

## Outcome

S01 completed. `_validate_relation_periods.py` is back at its 203-line
reviewability ceiling without raising the baseline.

## Notes

Verification:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_relation_periods.py src/aeat/domain/calculations/registry/test_registry_reviewability.py` passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q` passed: 3 tests.
