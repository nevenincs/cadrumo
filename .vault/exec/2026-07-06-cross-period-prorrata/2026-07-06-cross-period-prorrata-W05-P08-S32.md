---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S32'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# derive prorrata applicability evidence

## Scope

- `src/aeat/application/calculations/_prorrata_regularizacion.py`

## Description

- Re-read the live plan status and confirmed `W05.P08.S32` was the next open
  step after the S30/S31 formal deferrals.
- Attempted the required semantic search first; the port-8766 RAG service was
  stopped/stale and machine-owned by another process, so discovery continued with
  targeted grep and full file reads.
- Re-grounded the step against the cross-period prorrata ADR, the W05 plan row,
  the current prorrata register domain model, the existing volume-divergence
  rollup, and the current calculate-path advisory tests.
- Added `ProrrataApplicabilityProjection` and `derive_prorrata_applicability`
  as a pure fail-closed-to-visible projection over active register entries,
  declared annual sin-derecho volume, and ledger-projected sin-derecho volume.
- Added a new focused test file for register-active, declared-volume,
  ledger-projected, fully-taxable, and malformed-declared-volume cases without
  editing the existing dirty prorrata regression file.

## Outcome

- S32 is complete: prorrata applicability now has a reusable calculation-layer
  projection that returns `applies=True` when any non-`NINGUNA` register entry,
  declared sin-derecho annual volume, or ledger sin-derecho annual volume is
  present.
- The helper does not emit diagnostics yet; S33 and S34 remain responsible for
  calculate and verify advisories when applicability is true but the provisional
  percentage is unresolved.
- The application calculations facade was not edited because it currently has
  non-authored WIP unrelated to this step.

## Notes

- Verification passed: `uv run --no-sync ruff check
  src\aeat\application\calculations\_prorrata_regularizacion.py
  src\aeat\application\calculations\tests\test_prorrata_applicability.py`.
- Verification passed: `uv run --no-sync pytest -q
  src\aeat\application\calculations\tests\test_prorrata_applicability.py -n 0`
  (6 passed).
- Verification passed: `uv run --no-sync pytest -q
  src\aeat\application\calculations\tests\test_prorrata_regularizacion.py -n 0`
  (8 passed).
