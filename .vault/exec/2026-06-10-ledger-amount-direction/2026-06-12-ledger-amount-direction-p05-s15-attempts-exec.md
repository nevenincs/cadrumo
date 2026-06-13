---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S15'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Full Sequential Suite Attempts

## Scope

Step `P05.S15`.

## Attempts

- `uv run --no-sync pytest src/aeat -x -q` completed after 4700 passing tests, then failed at `src/aeat/application/modelo/tests/test_verificado_completo_regression.py::test_verify_grants_when_required_casillas_supplied_m130`. The failing test passed when rerun alone and when rerun as part of its module.
- A second `uv run --no-sync pytest src/aeat -x -q` attempt failed after 2577 passing tests at `src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories_part1.py::test_modelo_catalogue_defaults_isolate_bucket_writes`. The failing test also fails in isolation because a sibling modelo invariant now requires `external_evidence` for `ModeloRecord(aeat_accepted=True)`, while the migrated-repository fixture still builds accepted records without evidence.
- A follow-up isolated check of `src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories_part1.py::test_modelo_catalogue_defaults_isolate_bucket_writes` still fails with the same `ModeloRecord` validation error, so the full sequential gate remains predictably blocked before it can prove this child plan.

## Outcome

`P05.S15` is not complete. The open failure is outside the ledger amount/direction surface and should be resolved by the sibling modelo/persistence work owner or on a clean shared tree before this child plan is closed.
