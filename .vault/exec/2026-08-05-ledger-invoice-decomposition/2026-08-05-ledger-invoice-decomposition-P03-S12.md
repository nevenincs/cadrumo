---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:fe0e91d672e24fa35e420e75f61352a40a36f3b05b9669a09181107147bd2314'
step_id: 'S12'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Add the invoice retencion consistency validator, holding retencion outside the grand total

## Scope

- `src/cadrumo/domain/transactions`

## Description

- Add `_validate_retencion_consistency` to `Invoice` in `src/cadrumo/domain/invoices/_models.py:566`, a fourth after-validator beside the existing totals, FX and OSS validators.
- Refuse a negative retención amount, a rate outside the fractional 0..1 envelope, a rate declared without an amount, an amount exceeding the base imponible, and an amount disagreeing with its declared rate by more than one cent.
- Add `_RETENCION_TOLERANCE` at `src/cadrumo/domain/invoices/_models.py:50` with the reason a rate product needs slack the exact invoice-total sums do not.
- Add the `retention_amount_eur` accessor at `src/cadrumo/domain/invoices/_models.py:467`, mirroring the three existing euro total accessors.
- Add ten behavioural cases in `src/cadrumo/domain/invoices/tests/test_retencion_consistency.py`.

## Outcome

Landed as commit `974b7f91d6` (2 files, +253 lines, 0 deletions).

Raw counts, serial runs (`-n 0`): `test_retencion_consistency.py` 10 passed; the whole `domain/invoices/tests` package 117 passed after both Steps (97 before this Step). Tree-wide `pytest src/cadrumo --collect-only -q` collected 19930 of 23810 with no collection errors. `ruff check` and `ruff format --check` clean over the package.

The step scope as written named `src/cadrumo/domain/transactions`; the rich `Invoice` aggregate whose two unvalidated retención fields the step targets lives in `src/cadrumo/domain/invoices`, so the work landed there. `domain/transactions` already carries its own retención surface (the registry-backed RIRPF art. 95 rate loader and the row-level inference bound) and was not touched.

Two decisions the step did not specify, both recorded in the validator docstring:

The retención base is `base_total`, not `grand_total`. RIRPF art. 95.1 withholds "sobre los ingresos íntegros satisfechos" and the IVA repercutido is not an ingreso of the issuer (PGC NRV 12.a/14.a), so a rate checked against the IVA-inclusive total would over-state the expected withholding by the whole cuota. A test pins this by refusing `0.15` against `181.50`, which is exactly `15 %` of the grand total and exactly what a grand-total implementation would accept.

An amount may stand alone; a rate may not. The document frequently records what was withheld without recording the rate, so the amount is the declaration. A rate alone declares a proportion of nothing, and deriving the amount from it would manufacture a figure the document never stated.

## Notes

`retention_rate` had no declared unit at HEAD and two surfaces disagreed about it. The only in-tree construction of the field, the encrypted-storage roundtrip fixture, uses `0.15` against a base of `1000.00` with an amount of `150.00`, a fraction. The review-edit parser bounds `--set retention.rate` to the inclusive `0..100` percentage envelope and its tests assert `Decimal("15")`. The validator adopts the fractional convention, which is the one every other rate axis in the domain uses: `iva_rate_percentage` returns `pct / 100` and the registry RIRPF art. 95 rates are constrained `gt 0, lt 1`.

That divergence is currently latent, not live: nothing applies an `InvoiceEditSpec` to an `Invoice`, so no percentage reaches the field today. If that wiring is ever added, the new upper bound refuses `15` loudly instead of reading it as a 1500 % rate. Reported to the team lead as a coupling rather than fixed here, because the parser is outside this step's scope and its own boundary tests assert the percentage form.
