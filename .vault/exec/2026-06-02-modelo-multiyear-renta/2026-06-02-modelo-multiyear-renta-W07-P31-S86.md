---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S86'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write the M840 threshold-continuity E2E test asserting the 1M-per-year cifra-de-negocios exemption across two annual contexts via real adapters (vaultspec-standard-executor)

## Scope

- `src/aeat/application/calculations/test_modelo_840_exemption_continuity.py`

## Description

- Add a real Modelo 840 IAE threshold-continuity test across two annual contexts.
- Add a domain helper for the strict TRLRHL art.82.1.c net-turnover exemption threshold.
- Persist annual Modelo 840 observations with encrypted source metadata for INCN amount, threshold, exemption status, and legal refs.
- Assert below-threshold and equality-at-threshold behavior so the 1,000,000 EUR limit is strict.

## Outcome

- Satisfied by `test_modelo_840_iae_continuity.py` and the real `assess_modelo_840_iae_cifra_negocios_exemption` helper.
- The test proves 2024 below-threshold exemption and 2026 at-threshold non-exemption through real persistence and enrollment recording.
- Verified by `uv run --no-sync pytest -q -n 0 src/aeat/application/calculations/tests/test_modelo_840_iae_continuity.py`, which passed 5 tests.

## Notes

- The assessment covers only the art.82.1.c turnover exemption. Other IAE exemption pathways remain separate legal pathways.
