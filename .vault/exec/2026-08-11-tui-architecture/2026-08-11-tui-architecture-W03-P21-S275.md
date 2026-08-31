---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:7298d77efc97ba40c3f91305dc05de9955e9805727fcf0661dfa01d50204df12'
step_id: 'S275'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Extend the canonical calculation input surface to express explicit CLEAR_DECLARED_VALUE for manual scalar casillas, so an edit that withdraws a previously declared value reaches the engine through the same orchestrator every other input uses rather than a second write path, carrying its own axis on the content-addressed revision so a cleared casilla is provably distinguishable from one never declared

## Scope

- `the canonical calculate orchestrator input contract`
- `src/cadrumo/application/modelo/_edit_execution.py`
- `and focused clear-versus-never-declared tests`

## Changes

- `M` `src/cadrumo/domain/modelos/_calculation_revision.py`
- `M` `src/cadrumo/application/modelo/_revision_persistence.py`
- `M` `src/cadrumo/application/modelo/_calculation_actions.py`
- `M` `src/cadrumo/application/modelo/_edit_execution.py`
- `M` `src/cadrumo/application/modelo/_edit_models.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_execution.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_contract.py src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py src/cadrumo/adapters/persistence/profile/tests/test_modelos_edit_receipts.py src/cadrumo/domain/modelos/tests/test_calculation_revision.py -q -n 0 -m "integration or unit"` -> `pass` (101 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_modelo_210_agrupacion_renta_e2e.py src/cadrumo/application/modelo/tests/test_revision_replay_inputs.py src/cadrumo/domain/calculations/registry/tests/test_cross_boundary_roundtrip.py -q -n 0` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/domain/modelos/_calculation_revision.py src/cadrumo/application/modelo/_revision_persistence.py src/cadrumo/application/modelo/_calculation_actions.py src/cadrumo/application/modelo/_edit_execution.py src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/tests/test_edit_execution.py` -> `pass` (3 pre-existing unsound-assignment/unsound-return-statement diagnostics confirmed present before this change via git stash comparison; none introduced by it)
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/modelos/_calculation_revision.py src/cadrumo/application/modelo/_revision_persistence.py src/cadrumo/application/modelo/_calculation_actions.py src/cadrumo/application/modelo/_edit_execution.py src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/tests/test_edit_execution.py` -> `pass`

## Notes

`cleared_casilla_ids` is a new optional identity axis on `CalculationRevision`
and `derive_calculation_revision_id`: when empty it contributes no payload
key, so every existing precomputed revision id is byte-identical to before
this change (confirmed by the full `test_calculation_revision.py` and replay
suites passing unmodified). `REMOVE_OVERRIDE` stays `NOT_YET_WIRED` in
`ModeloEditUnsupportedIntentReason`; only `CLEAR_DECLARED_VALUE_NOT_YET_WIRED`
was retired from that enum, since only the clear axis is in this Step's scope
per the re-scoped plan action.

`RELEASED_FORMAT_FLOORS` is `None` while `COMPATIBILITY_REGIME` is
`PRE_RELEASE` (`core/compatibility_lifecycle.py`), so this persisted-shape
change needed no durability-floor update and no upgrader.
