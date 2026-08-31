---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ee940f724440332934fac51a271f5b5d7694b4be351781f320465cc260900cff'
step_id: 'S135'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Replace calculation-revision persistence with guarded work-and-calculation compare-and-swap so duplicate-existing and new-revision branches recheck the same edit baseline and co-commit immutable revision, work pointer, lifecycle event, and edit result receipt without any unguarded pointer advance

## Scope

- `src/cadrumo/application/modelo/_revision_persistence.py`

## Changes

- `M` `src/cadrumo/application/modelo/_revision_persistence.py`
- `A` `src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py -q -n 0 -m integration` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_modelo_210_agrupacion_renta_e2e.py -q -n 0` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_revision_persistence.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_revision_persistence.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py` -> `pass`

## Notes

Extends the existing single-writer primitive `persist_calculation_revision`
in place rather than replacing it wholesale: the duplicate-existing branch's
previously-unguarded `work_unit_repository.save(...)` pointer advance is now
`save_with_secure_object_writes(..., expected_revision_id=work_units_revision_id)`,
the same compare-and-swap guard the new-revision branch already used, and
both branches accept an optional `additional_secure_object_writes` tuple so
a caller (the edit executor Step) can co-commit an edit result receipt in
the SAME transaction without this function knowing its payload shape. The
one existing caller (`_calculation_actions.py`) is unaffected: the new
parameter defaults to empty. Baseline reconfirmation itself
(`reconfirm_modelo_edit_baseline` from the S133 admission/preflight module)
is intentionally left to the edit-execution Step, which is the guarded
commit point per the ADR; this Step provides the persistence-side compare-
and-swap fix and co-commit hook it depends on.

Proved the duplicate-branch guard fix bites: reverted it locally to the
prior unguarded `.save`, confirmed
`test_duplicate_branch_refuses_a_real_conflicting_pointer_write` failed
(`DID NOT RAISE SecureObjectRevisionConflictError`), then restored the fix
and confirmed the suite passes again. Diff was clean (git diff) both before
and after restoring.
