---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:0f6d14a18c89be4221923834bffc70c315cf828204f482f02e65a6ddb480be9a'
step_id: 'S42'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Let the invoice carry a suplido, which joins total and cash while joining neither base nor cuota, taking a third position on the identity rather than a second recargo

## Scope

- `src/cadrumo/domain/invoices/_models.py`
- `src/cadrumo/domain/invoices/_decomposition.py`

## Description

- Add nullable `suplido_amount: Decimal | None` to `Invoice`, plus a `suplido_amount_eur` accessor mirroring `recargo_amount_eur`.
- Move the totals identity to `grand_total == base_total + iva_total + recargo_amount + suplido_amount`; extend the all-exempt branch to `grand_total == base_total + suplido_amount`.
- Add a consistency validator refusing a negative suplido; unlike recargo, no upper bound (a suplido carries no statutory rate) and no taxable-supply restriction (a suplido may accompany an exempt operation).
- Extend `InvoiceComponents` with a required `suplido` field and fold it into `total` in `decompose_invoice`.
- Correct the module docstrings in `_models.py` and `_decomposition.py` stating the pre-suplido identity.
- Add `suplido_amount` to the strict-mode JSON->Decimal coercion loop, alongside a pre-existing gap on `recargo_amount` found and fixed in the same edit (see Notes on the S41 record).

## Outcome

Landed as commit `1751ce04cf` (combined with P06.S41, S43-S45; see the S41 record's Notes for why).

A gestor or similar issuer can now record a disbursement paid on the client's behalf under LIVA art. 78.Tres.3.º. `None` and `Decimal("0")` stay distinct, matching the recargo precedent: unrecorded and none-arose are different statements. Decomposition of a grounded record with both recargo and suplido yields `total = taxable_base + cuota + recargo + suplido`; both third-position terms accumulate independently.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/invoices/tests/test_invoice_suplido.py -n 0 -q --no-header
11 passed in 2.49s
```

```
uv run --no-sync pytest src/cadrumo/domain/invoices -n 0 -q --no-header
174 passed in 6.04s
```

Two mutation-proof passes, both on a copy of the source restored byte-exact afterwards (SHA-256 verified):

- Dropping `+ suplido` from `Invoice`'s `grand_total` identity check reddens 11: the whole `test_invoice_suplido.py` file plus `test_secure_storage_roundtrip.py`'s populated-fixture roundtrip test, nothing else (11 failed, 163 passed).
- Dropping `+ self.suplido` from `InvoiceComponents._validate_identity` in `_decomposition.py` reddens exactly the 3 tests asserting the decomposed `total`/`cash` figures (3 failed, 171 passed).

## Notes

See the S41 record for the shared commit rationale, the two absorbed downstream ripples, and the peer-commit interaction on `application/aggregation`.
