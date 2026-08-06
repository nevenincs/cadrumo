---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:c18f211f67eb5f842cd8494c1d9b717f7885143c3ea6f14079526658e5ece72e'
step_id: 'S14'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

# add a real-CLI end-to-end test that a sole-trader's M100 casilla 0171 / 0180 / 0224 populate from the ledger unaided

## Scope

- `src/aeat/application/modelo/tests/`

## Description

Extended the existing real-CLI Modelo 100 source-mesh test so the public
`aeat app modelo work calculate` path now asserts all three S14 activity-chain
casillas. The test already seeded a natural-person actividad-economica profile,
persisted real ledger income and deductible expense rows, created a Modelo 100
work unit through the CLI, and calculated it through the CLI without supplying
manual values for the named casillas. This pass added the missing `0180`
assertion beside the existing `0171` and `0224` assertions.

## Outcome

W02.P05.S14 complete. The real CLI test proves the sole-trader M100 annual
ledger path populates `0171`, `0180`, and `0224` from source-owned ledger
evidence, while unrelated expense assertions continue to cover `0218` and
`0220`.

## Notes

Verification on 2026-07-02:
`uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py::test_work_calculate_modelo_100_routes_marta_auto_ledger_expenses`
passed, 1 test. Full output is in `_scratch-wave1-d9/s14-m100-cli.log`.

The originating plan row names `src/aeat/application/modelo/tests/`, but the
project's real CLI harness for this behavior already lives in
`src/aeat/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`; this
record follows the executable real-CLI evidence surface rather than duplicating
the harness in an application-layer folder.
