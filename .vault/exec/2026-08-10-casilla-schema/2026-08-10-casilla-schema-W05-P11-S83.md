---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:92605b1fbd3fdcbcf6d231a6e6baf77750f0dc3e62730002ab8697f360977df3'
step_id: 'S83'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# repair the real M303-quarter-to-M390 end-to-end suite to law-select each live split M303 revision and make all four scenarios pass without restoring or tolerating the retired revision id

## Scope

- `src/cadrumo/application/modelo/tests/test_e2e_ledger_m303_quarters_to_m390_annual.py`

## Description

- Select every quarterly M303 work-unit revision through the validated registry authority using the filing year and typed period.
- Remove the retired `2023-y-siguientes` fixture token without an alias, fallback, or mirrored selector.
- Align the real export checks with the live revisions' filing-grade layout withdrawal and retain the local filing-to-M390 reconciliation path.
- Match the cross-period advisory assertion to the production relation origin code.

## Outcome

All four real encrypted-SQLite end-to-end scenarios pass. The suite exercises both 2024 split revisions (`2024-hasta-08-y-2t` and `2024-desde-09-y-3t`) and the 2025 revision through production law selection. Verification, local filing, observation persistence, M390 annual fold-in, and typed withdrawn-export refusals remain live-behaviour assertions.

`ruff format --check` and `ruff check` pass for the target. `basedpyright` reports zero errors, warnings, or notes. The exact module reports four passing tests. The target contains no retired revision token.

## Notes

The repository-wide retired-revision structural gate remains red outside this Step's scope: ten occurrences remain across `test_modelo_303_deductible_evidence_gate.py`, `test_modelo_303_official_box_under_declaration.py`, `test_diff.py`, `test_modelo_180_round_trip.py`, and `test_modelo_reconcile_verb.py`. Those pre-existing or concurrent paths were not modified. No data loss or destructive Git operation occurred.
