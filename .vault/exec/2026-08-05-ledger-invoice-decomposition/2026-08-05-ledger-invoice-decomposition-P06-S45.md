---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:3c6aee3125babbed2d1d3ae6449f6c48b084738b48908e93457b843931e448f0'
step_id: 'S45'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Represent pagos anticipados so a prepayment devengues on collection for the amount received, honouring the article 25 exclusion

## Scope

- `src/cadrumo/domain/invoices/_models.py`
- `src/cadrumo/application/aggregation`

## Description

- Represent LIVA art. 75.Dos pagos anticipados on the SAME `operation_date` / `operation_date_role` axis P06.S41 added (`ADVANCE_PAYMENT_RECEIVED` role), rather than a second date field: art. 75.Dos's collection date and art. 75.Uno's operation date are both, mechanically, "the recorded devengo-relevant date" -- the role changes which clause supplied it, not how it is read.
- Add a model validator refusing `ADVANCE_PAYMENT_RECEIVED` when `iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY` (the art. 75.Dos párrafo segundo exclusion for art. 25 entregas) and when `payment_status` is not `PAID`/`PARTIALLY_PAID` (art. 75.Dos requires actual cobro, "total o parcial").
- Add `application/aggregation/_invoice_devengo.py` exposing `invoice_devengo_date(invoice) -> date`: returns `invoice.operation_date or invoice.issued_at`, re-exported from the package facade.

## Outcome

Landed as commit `1751ce04cf` (combined with P06.S41-S44; see the S41 record's Notes for why).

A fully- or partially-collected advance payment can now be recorded and devengues on the collection date rather than the issue-date proxy; the art. 25 exclusion and the "money was actually collected" precondition are both enforced at construction time, so a record reaching `invoice_devengo_date` under this role is already legally consistent. Threading this date into an actual quarter's IVA period-attribution selection (the ledger-transaction equivalent already exists in `domain.transactions.transaction_eligible_date_span`) is separate, later work -- named explicitly in this Step's own plan text as P06.S48 -- and is not attempted here; `invoice_devengo_date` is the fact that wiring will read.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/invoices/tests/test_invoice_pagos_anticipados.py src/cadrumo/application/aggregation/tests/test_invoice_devengo.py -n 0 -q --no-header
10 passed in 5.56s
```

```
uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/application/aggregation src/cadrumo/application/invoices src/cadrumo/application/ledger src/cadrumo/entrypoints/cli src/cadrumo/domain/iva src/cadrumo/domain/transactions -n auto -q --no-header
2743 passed in 64.42s
```

Mutation-proof (on `_models.py`, restored byte-exact afterwards and verified by SHA-256 match):

- Removing the art. 25 exclusion check reddens exactly `test_the_article_25_exclusion_refuses_an_advance_payment_devengo` (1 failed, 6 passed in the file), nothing else -- proven against the control `test_the_same_amounts_devengue_normally_without_the_advance_payment_role`, which stays green, confirming the exclusion is keyed on the role and not on the category alone.

`application/aggregation/_invoice_devengo.py` is a pure read of a construction-time-guarded fact and carries no independent branch to mutate; its own tests (`test_an_undated_invoice_falls_back_to_the_issue_date_proxy`, `test_a_recorded_operation_date_takes_precedence_over_the_issue_date`, `test_a_pago_anticipado_collection_date_is_read_identically`) pin its one line of logic directly.

## Notes

See the S41 record for the shared commit rationale and the peer-commit interaction on `application/aggregation`.

**Staged/partial pagos anticipados are out of scope, named explicitly rather than silently dropped.** The single `operation_date` field represents one devengo-shifting event -- correct for the common case of a fully-prepaid invoice -- but LIVA art. 75.Dos's "cobro total o parcial" also covers a SERIES of partial advance payments, each devengoing separately for its own collected amount, which is a materially different shape (a dated-amount schedule, closer to `domain.transactions.IvaCashAccountingPaymentEvidence`) than a single date can carry. The originating ADR (`2026-08-05-ledger-invoice-decomposition-adr`, D10) names this explicitly as "not representable today ... named work, not an assumption"; this Step closes the single-event case only.
