---
tags:
  - '#audit'
  - '#registry-row-width-pressure'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-registry-row-width-pressure-plan]]'
---

# `registry-row-width-pressure` audit: `verification blocker`

## Status

The active plan remains open at `P03.S06`. The row-width implementation steps
through `P02.S05` are committed and pushed, but final plan verification cannot
be closed in the current shared worktree because an unrelated dirty validator
module exceeds its existing reviewability ceiling.

## Passing gates

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`: 27 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q`: 41 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_record_design.py -q`: 41 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`: 37 passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-registry-row-width-pressure-plan.md`: passed.

## Blocking gate

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q`
currently returns 1 failed, 2 passed. The failing assertion is
`test_registry_validator_modules_stay_below_p05_reviewability_baseline`:

- `_validate_relation_periods.py`: 217 lines exceeds the existing 203-line
  baseline.

The scoped diff shows that `src/aeat/domain/calculations/registry/_validate_relation_periods.py`
has unrelated concurrent docstring edits. This row-width slice did not edit
that file and should not adjust its validator-module baseline.

## Next action

Resolve or commit the validator-module reviewability work in its owning slice,
then rerun `P03.S06`. If the full reviewability gate passes, close `S06` with
a normal exec step record and proceed to `P03.S07` review.
