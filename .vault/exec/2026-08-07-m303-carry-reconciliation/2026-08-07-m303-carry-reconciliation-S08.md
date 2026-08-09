---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:6278bd92f4ab104ab555512d60ea37d9ac072739f82f38277072223c2ad5dd4b'
step_id: 'S08'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
# IMPLEMENTED - validated observation-envelope IVA wallet recurrence

## Scope

- `src/cadrumo/application/modelo/_iva_wallet_gate.py`
- `src/cadrumo/application/calculations/_iva_wallet_reconciliation.py`
- `src/cadrumo/application/modelo/tests/test_iva_wallet_engine_integration.py`
- `src/cadrumo/tests/test_decimal_enrollment_inventory.py`

## Description

- Replaced the prior calculated-revision casilla read with a recurrence derived only from the exact prior Modelo 303 `ObservationEnvelopePayload`.
- Refused missing, legacy, conflicting, coordinate-mismatched, and revision-stamp-mismatched envelopes before they can establish carry.
- Kept the IVA wallet as the carry authority; a prior calculation revision is used only to validate the envelope stamp.
- Revalidated persisted envelope-backed local and filed-history decisions before replay, while retaining settled live-wallet and taxpayer-override decisions.

## Outcome

Refunded prior periods contribute zero, compensated periods contribute their validated available amount, and stale or contradictory prior filing evidence fails closed. A taxpayer override with an envelope-like free-form locator remains settled rather than being reclassified as source recurrence.

## Verification

`uv run --no-sync ruff check` on the four changed source and test files: passed.

`uv run --no-sync basedpyright` on the changed wallet gate and integration test: `0 errors, 0 warnings, 0 notes`.

`uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_iva_wallet_engine_integration.py -q`: `15 passed`.

`uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_iva_wallet_reconciliation.py src/cadrumo/application/modelo/tests/test_iva_wallet_engine_integration.py -q`: `38 passed`.

`uv run --no-sync pytest src/cadrumo/tests/test_decimal_enrollment_inventory.py -q`: `16 passed`.

The S05-S07 regression lane passed with `68 passed` before the replay remediation. Its post-remediation rerun is unverified because concurrent Modelo 100 registry work fails shared registry validation before the targeted M303 test bodies execute.

## Notes

Formal review approved after resolving the persisted zero replay and prefixed taxpayer-override provenance findings.
