---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:33824712f563f3961d44eeae26c6616c5c1687833b3def7b98b80616ef67ad3a'
step_id: 'S23'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add the pull==calculate parity regression proving the apportioned deducible casilla resolves identically on the calculate path and the Sheets-pull path (one-aggregation-path-pull-equals-calculate)

## Scope

- `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`

## Description

- Ground S23 with semantic search over the pull/calculate parity surface, then
  read the existing parity module, M303 bucket-aggregation tests, and source
  mesh resolver implementation.
- Add a real M303 prorrata parity regression that seeds encrypted runtime
  repositories with a work unit, two IVA ledger rows, an IVA-wallet zero
  decision, and an active `general` prorrata register entry.
- Compare the live bucket-aggregation calculate path against the direct
  `LedgerIvaAggregationSourceResolver` plus `calculate_registry_snapshot` pull
  shape used by the existing parity module.
- Assert the apportioned deducible binding is non-zero and below the source
  purchase cuota, the live persisted binding override equals the resolver
  value, the semantic deducible casilla equals that value, and official box `29`
  matches on both paths.
- Record the S23 implementation review in the feature audit with no open
  findings.

## Outcome

- The W03.P05 parity slice now proves the apportioned M303 deducible cuota
  resolves identically through the live calculate mesh and the standalone
  pull-path shape, preserving the one shared IVA ledger aggregation path.
- The regression uses the existing `ledger_iva_aggregation` resolver and source
  kind; no new source kind, resolver convention, validator convention, or
  registry selector shape was introduced.

## Notes

- Verification passed: `uv run --no-sync ruff check src\aeat\application\calculations\tests\test_pull_path_calculate_path_casilla_parity.py`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_pull_path_calculate_path_casilla_parity.py -k prorrata -n 0` (1 passed, 1 deselected).
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_pull_path_calculate_path_casilla_parity.py -n 0` (2 passed).
