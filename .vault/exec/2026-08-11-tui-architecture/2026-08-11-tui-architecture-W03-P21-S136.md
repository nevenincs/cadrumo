---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:87ec2a6615f15908bf224d911652d4a6e42881ad67a8177233e0f7927017231b'
step_id: 'S136'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Implement the application-owned edit executor that rechecks every ModeloEditBaselineV1 coordinate at the guarded commit point, refuses stale or incompatible intent without rebasing, delegates canonical calculation and guarded persistence, and returns only typed result receipts

## Scope

- `src/cadrumo/application/modelo/_edit_execution.py`

## Changes

- `A` `src/cadrumo/application/modelo/_edit_execution.py`
- `A` `src/cadrumo/application/modelo/tests/test_edit_execution.py`
- `A` `src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py`
- `M` `src/cadrumo/application/modelo/_edit_models.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py -q -n 0 -m integration` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py src/cadrumo/adapters/persistence/profile/tests/test_modelos_edit_receipts.py -q -n 0 -m "integration or unit"` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_modelo_210_agrupacion_renta_e2e.py -q -n 0` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_edit_execution.py src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py` -> `pass`

## Notes

V1 scope per team-lead ruling (option 1): CALCULATE mutation family with
SET_TYPED_VALUE scalar intents only, the only shape the shared calculation
boundary (`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`)
accepts today. Every other syntactically admitted intent (RECALCULATE,
CLEAR_DECLARED_VALUE, REMOVE_OVERRIDE, and all four row-intent kinds) refuses
with its own `ModeloEditUnsupportedIntentReason` member naming the specific
intent -- never one generic "unsupported" bucket -- added to `_edit_models.py`
in this Step alongside the dedicated `ModeloEditUnsupportedIntentRefusalV1`.

Reasons are named for the missing capability, not for the plan Step that will
supply it (`W03.P21.S275` for CLEAR_DECLARED_VALUE/REMOVE_OVERRIDE,
`W03.P21.S276` for the row intents): a Step id is process metadata and this
reason ships inside the public V1 contract, and the source-hygiene rule
forbids process labels in production schemas. The Step-to-reason mapping is
recorded here, in the Step Record, per "traceability lives in the Step
Record, which cites the code, never the reverse."

Commit-point discipline: `reconfirm_modelo_edit_baseline` runs immediately
before delegating to the calculation boundary, using catalogues loaded at
that point (not the caller's). `test_edit_commit_point_guard.py` proves the
window between a passed reconfirm and the guarded write is closed by driving
a real second writer into it; `test_edit_execution.py`'s own race test proves
the same property through `apply_modelo_edit` end to end.
