---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S27'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# prove prorrata settlement projection and year carry

## Scope

- `src/aeat/application/calculations/tests/test_prorrata_regularizacion.py`

## Description

- Rename and tighten the M303/M390 projection regression so the definitive percentage is explicitly the declared annual-volume value supplied to the regularización projection.
- Keep the ledger-rollup contradiction regression asserting declared annual volume casillas retain authority while the advisory fires.
- Add a real encrypted-repository settlement integration that files an M303 2026 4T revision, co-emits the prorrata register write-back, persists the filed observation, and evaluates the 2027 carried-prior-definitive seed from that stamped observation.
- Use registry-grounded M303 observations for the settlement fixture rather than invented legal/source provenance.

## Outcome

- S27 is implemented as tests only.
- The focused test file now proves casilla 44 projects from the supplied declared-volume definitive percentage, the ledger contradiction advisory remains non-blocking with declared authority preserved, and the filing transition supplies a valid year+1 carried-prior-definitive seed.
- No new binding source kind, resolver convention, validator convention, or registry selector shape was introduced.

## Notes

- Verification: `uv run --no-sync ruff check src\aeat\application\calculations\tests\test_prorrata_regularizacion.py`.
- Verification: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_prorrata_regularizacion.py -n 0` passed with 8 tests.
- Verification: `uv run --no-sync pytest -q src\aeat\application\prorrata_register\tests\test_seed.py -n 0` passed with 3 tests.
- Verification: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_prorrata_settlement_writeback.py -n 0` passed with 3 tests.
