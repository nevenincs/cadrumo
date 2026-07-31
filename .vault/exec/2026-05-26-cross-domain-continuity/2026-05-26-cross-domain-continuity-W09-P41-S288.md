---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:3029ab337e287e399afc3cf23ee5e86a58aee1cd464b11270f98038807f92571'
step_id: 'S288'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Close duplicate criterio de caja cash-accounting split

## Scope

- `model the Ley 37/1992 art 163 quinquies cash-accounting regime`
- `separate from the intracom axes work`
- `out-of-scope for W05.P24 - surface as W09 or future-wave candidate`
- `src/aeat/application/aggregation/`

## Description

- Re-ran the required RAG discovery for criterio de caja/casilla 62 against
  vault records and code.
- Reviewed accepted ADR `2026-07-06-cross-domain-continuity-adr`, S287, and
  S281 execution records.
- Confirmed S281 already landed the cash-accounting regime/payment-evidence
  axis as a non-`IvaCategory` dimension.
- Confirmed the implementation binds the full Modelo 303 cash-accounting
  informational box set, not only the originally mentioned box 62.
- Re-ran focused cash-accounting aggregation and committed-registry tests.

## Outcome

S288 is closed as superseded by S281/S287. No code change was made in this
record.

The original S288 row was opened when casilla 62 was explicitly excluded from
the W05.P24 intracom/export axis work. That split was later resolved by:

- S287: accepted the modelling decision that criterio de caja is an independent
  timing/reporting/payment-evidence axis;
- S281: implemented the axis in transactions, IVA aggregation observations,
  ledger binding selectors, legal catalogue data, and Modelo 303 bindings;
- S281: bound Modelo 303 casillas 62/63 for supplies and 74/75 for acquisitions
  in both committed M303 revision families.

Verification:

- `uv run --no-sync pytest -q src/aeat/application/aggregation/tests/test_iva_cash_accounting.py src/aeat/domain/calculations/registry/tests/test_modelo_303_cash_accounting.py`
  passed: 4 tests.

## Notes

Residual edge not claimed here: wholly unpaid fallback-only cash-accounting
operations remain intentionally rejected unless payment evidence exists. That
is the S281 contract and prevents silent projection from invoice date alone.
