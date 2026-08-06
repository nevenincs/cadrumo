---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:548eece1b1a2ad2a180cefc308e6f3186d9499a228c1565c23392fe13ffb28b3'
step_id: 'S34'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add the settlement-period verify ADVISORY predicate so the gate never grants verified_complete with zero findings on an applies-but-unresolved prorrata, mirroring the Modelo 200 implies_nonzero worked example (no-silent-under-declaration)

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/`
- `src/aeat/application/modelo/tests/test_verification_m303_prorrata_advisory.py`

## Description

- Re-read the live plan status and confirmed `W05.P08.S34` remained the next open step after S33.
- Re-grounded the step with semantic search, the W05 plan row, the cross-period prorrata ADR, the existing M303 `implies_nonzero` advisory, and the live verification-predicate runtime.
- Added a fragmented M303 2023 verification expectation that emits an ADVISORY when annual prorrata volume is declared but casilla 44 is zero/absent.
- Kept the predicate on the existing `implies_nonzero` DSL shape: no new verification operator, source kind, resolver convention, validator convention, or source-mesh path was introduced.
- Added a focused application test that loads the shipped M303 revision, evaluates the live predicate, proves the warning is non-blocking, proves a non-zero casilla 44 satisfies it, and proves the Art. 94 no-volume full-deduction default stays silent.

## Outcome

- S34 is complete: settlement verification no longer grants a zero-finding result when an operator has declared annual prorrata volume but left casilla 44 unresolved.
- The advisory is intentionally non-blocking because a zero regularizacion may be legitimate after the provisional carry and definitive calculation are confirmed.
- The change remains scoped to the M303 fragmented verification expectation and its real predicate evaluation test.

## Notes

- Verification passed: `uv run --no-sync ruff check src\aeat\application\modelo\tests\test_verification_m303_prorrata_advisory.py`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_verification_m303_prorrata_advisory.py -n 0` (4 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_verification_m303_regimen_simplificado_advisory.py src\aeat\application\modelo\tests\test_verification_m303_prorrata_advisory.py -n 0` (8 passed).
- Verification passed: `uv run --no-sync vaultspec-core vault check features --feature cross-period-prorrata`.
