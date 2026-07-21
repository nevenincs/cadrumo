---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S35'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add tests proving a mixed trader can no longer silently deduct 100% in-year, silently skip casilla 44, or silently zero the deducible side, while a fully-taxable trader keeps the art-94 full-deduction default untouched

## Scope

- `src/aeat/application/calculations/tests/test_prorrata_regularizacion.py`

## Description

- Re-read the live plan status and confirmed `W05.P08.S35` was the next open step after S34.
- Re-grounded the step against the S32 applicability projection, S33 missing-carry diagnostic, S34 verification predicate, the existing annual regularizacion projection tests, and the M303 full-deduction default registry comment.
- Added a calculation-layer regression proving a mixed trader with declared sin-derecho volume and unresolved provisional carry emits the missing-carry advisory instead of silently defaulting to a 100 percent in-year deduction.
- Added a settlement regression proving a zero-percent definitive prorrata still surfaces a casilla-44 regularizacion advisory instead of silently zeroing the deducible side.
- Added a fully-taxable no-volume regression proving the Art. 94 full-deduction default produces no missing-carry or regularizacion advisory noise.
- Kept the S34 live verification-predicate test as the explicit proof that a mixed trader cannot silently skip casilla 44 at verify time.

## Outcome

- S35 is complete: the calculation regression surface now names the mixed-trader non-silence cases and the fully-taxable no-volume quiet path.
- No production code changed; the step only adds assertions over shipped calculation and verification behavior.

## Notes

- Verification passed: `uv run --no-sync ruff check src\aeat\application\calculations\tests\test_prorrata_regularizacion.py`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_prorrata_regularizacion.py -n 0` (11 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_prorrata_regularizacion.py src\aeat\application\calculations\tests\test_prorrata_missing_carry.py src\aeat\application\modelo\tests\test_verification_m303_prorrata_advisory.py -n 0` (19 passed).
