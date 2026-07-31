---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:48fc454d1f7c2001048a2101594235c7646e2a01dbc6ae86840d04e7b0d1a3d6'
step_id: 'S88'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the removed MultiYearResolver orphan: confirm no live resolver claim remains, preserve live PreviousFilingSourceResolver and carry-gate coverage, and defer any future multi-year scanner until it has a real caller (vaultspec-high-executor)

## Scope

- `src/aeat/application/calculations/_multi_year.py`
- `src/aeat/application/calculations/tests/test_carry_gate_parity.py`
- `.vault/exec/2026-06-26-binding-fold-in-carry-unification/2026-06-26-binding-fold-in-carry-unification-P04-S16.md`
- `.vault/exec/2026-06-26-binding-fold-in-carry-unification/2026-06-26-binding-fold-in-carry-unification-P04-S17.md`

## Description

- Reconcile the stale `MultiYearResolver.resolve()` row against the current binding-fold-in carry decision.
- Ground the row with `uvx vaultspec-rag search "MultiYearResolver removed PreviousFilingSourceResolver resolver tests docstring claim" --type code --limit 12` and `rg -n "MultiYearResolver|resolve_prior_year_observations" .vault src`.
- Confirm `MultiYearResolver` and `resolve_prior_year_observations` were deleted by the binding-fold-in carry unification campaign as a confirmed orphan with no live caller.
- Confirm `_multi_year.py` now keeps only the live enrollment recorder and `PreviousFilingSourceResolver` surfaces.
- Confirm live R2 carry-gate behavior is covered by `test_carry_gate_parity.py`; do not recreate the deleted resolver without a real caller.

## Outcome

- `.vault/exec/2026-06-26-binding-fold-in-carry-unification/2026-06-26-binding-fold-in-carry-unification-P04-S16.md` records the resolver deletion and removed redundant tests.
- `.vault/exec/2026-06-26-binding-fold-in-carry-unification/2026-06-26-binding-fold-in-carry-unification-P04-S17.md` records the post-deletion import and carry-gate verification.
- `uv run --no-sync pytest -q -n 0 src\aeat\application\calculations\tests\test_carry_gate_parity.py`: 3 passed.
- No production source changed in this reconciliation pass.

## Notes

- This row is closed as stale-by-supersession. Future multi-year scanning must be reintroduced as live code with a caller and tests, not as an orphan resolver.
