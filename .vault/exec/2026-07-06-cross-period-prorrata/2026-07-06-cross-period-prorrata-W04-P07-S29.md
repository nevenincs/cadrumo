---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:5edff54e8951384ab7bfc08a03003a971a2fd9daee1130f55217ff4b98b363c6'
step_id: 'S29'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# prove prorrata regularizacion manual oracle

## Scope

- `src/aeat/application/calculations/tests/test_prorrata_regularizacion_oracle.py`

## Description

- Re-read the live plan status and confirmed `W04.P07.S29` remained the next
  authoritative open step after the S28 correction.
- Re-grounded the step through semantic search, the W04/P07 plan row, the
  cross-period prorrata ADR, the corrected manual-oracle payload, the current
  prorrata projection code, and the Modelo 303 registry runtime tests.
- Added a focused oracle proof that loads the S28 payload, computes the current
  definitive percentage through the real M303 2025 `4T` registry snapshot, and
  compares it with the bundled AEAT figure.
- Seeded the manual's prior-year volumes through the prorrata domain substrate
  to produce the manual-stated provisional percentage, then fed the existing
  application projection with the manual's first-three-quarter input IVA.
- Proved the standalone casilla 44 regularizacion, fourth-quarter current
  deduction, fourth-quarter net effect, and annual deduction total against the
  AEAT manual figures rather than values derived from the formula under test.

## Outcome

- S29 is complete: the annual prorrata-general regularizacion chain now has an
  end-to-end AEAT Manual practico IVA oracle proof.
- The proof keeps declared annual-volume authority intact: the definitive
  percentage comes from M303 volume casillas and the current promotion boundary
  remains unchanged.
- The test explicitly separates Modelo 303 casilla 44's standalone
  regularizacion amount (`-217.60`) from the manual's net fourth-quarter
  deduction effect (`-128.00`), preventing the two figures from being conflated
  during S30 promotion.

## Notes

- Verification passed: `uv run --no-sync ruff check
  src\aeat\application\calculations\tests\test_prorrata_regularizacion_oracle.py`.
- Verification passed: `uv run --no-sync pytest -q
  src\aeat\application\calculations\tests\test_prorrata_regularizacion_oracle.py
  -n 0` (1 passed).
- Verification passed: `uv run --no-sync pytest -q
  src\aeat\application\calculations\tests\test_prorrata_regularizacion.py -n 0`
  (8 passed).
- Verification passed: `uv run --no-sync pytest -q
  src\aeat\domain\calculations\registry\tests\test_external_oracle_grounding_enrolled.py
  -n 0 -m integration` (2 passed).
