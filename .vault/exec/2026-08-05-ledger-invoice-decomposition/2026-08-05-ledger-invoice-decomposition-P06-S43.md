---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:45d70f35b67aafe6bb3b8e3eb995487fea6f59daf6b73160b7d60b4b0e9cd192'
step_id: 'S43'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Let a factura rectificativa name what it corrects, so the cuota rectification LIVA article 89 requires becomes representable

## Scope

- `src/cadrumo/domain/invoices/_models.py`

## Description

- Add an `InvoiceClass` enum (`ORDINARIA`, `SIMPLIFICADA`, `RECTIFICATIVA`) to `_enums.py`; `Invoice.invoice_class` defaults to `ORDINARIA`, preserving every existing invoice's implicit class.
- Add nullable `series: str | None` (general RD 1619/2012 art. 6.1.a concept, permitted on any class) and `rectifies_invoice_number: str | None` (only meaningful on a rectificativa) to `Invoice`.
- Add a consistency validator: a `RECTIFICATIVA` requires both `series` (art. 6.1.a.2.º's mandatory specific series) and `rectifies_invoice_number` (LIVA art. 89's requirement to name what is corrected); any other class refuses a stray `rectifies_invoice_number`.

## Outcome

Landed as commit `1751ce04cf` (combined with P06.S41-S42, S44-S45; see the S41 record's Notes for why).

A factura rectificativa can now name the invoice it corrects and be issued in its own series, both previously unrepresentable since the invoice record carried no class axis at all.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/invoices/tests/test_invoice_rectificativa.py -n 0 -q --no-header
6 passed in 2.42s
```

```
uv run --no-sync pytest src/cadrumo/domain/invoices -n 0 -q --no-header
174 passed in 6.04s
```

Mutation-proof: removing the whole `if self.invoice_class is InvoiceClass.RECTIFICATIVA: ... elif self.rectifies_invoice_number is not None: raise ...` block reddens exactly the 3 tests targeting it (`test_a_rectificativa_with_no_series_is_refused`, `test_a_rectificativa_naming_nothing_it_corrects_is_refused`, `test_a_stray_rectification_reference_on_an_ordinaria_is_refused`; 3 failed, 3 passed in the file), nothing else. `_models.py` restored byte-exact afterwards, verified by SHA-256 match.

## Notes

See the S41 record for the shared commit rationale, the two absorbed downstream ripples, and the peer-commit interaction on `application/aggregation`.

**Case 3.º of art. 6.1.a's mandatory-series list (destinatario-issued or third-party-issued invoices) is not modelled.** Only the rectificativa case (2.º) is enforced here, since it is the only one this Step's brief named and the only one the invoice record currently has a field to represent the counterpart fact for (`invoice_class`). The other art. 6.1.a mandatory-series cases remain unrepresented, matching the same honesty posture as the art. 6.1.d case 3.º carve-out on S44.
