---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:6ae78f77349ff2371dc62d6ae51ac604a4e3540e87c228004893fad9d732674b'
step_id: 'S50'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Refuse a suite of deliberately degraded invoices, each asserting its own specific refusal rather than that something failed, covering the falsified-total, netted-retencion, contradicted-operation-date, referentless-rectificativa and over-threshold-simplificada cases

## Scope

- `src/cadrumo/domain/invoices/tests`

## Description

- Investigated all five named cases against the current `Invoice` model
  (landed by the prior commits adding `operation_date` /
  `InvoiceOperationDateRole`, `suplido_amount`, `InvoiceClass` / `series` /
  `rectifies_invoice_number`, and the conditional `counterparty_tax_id`).
- Found four of the five cases already implemented as pinned, polarised
  guards with a truthful companion, each in its own axis-scoped test file:
  falsified total (`test_invoice_suplido.py::test_dropping_the_suplido_from_the_total_is_refused`
  and the sibling `test_invoice_recargo_equivalencia.py::test_dropping_the_recargo_from_the_total_is_refused`,
  plus `test_models.py`'s line-sum-vs-`base_total` variant), netted retención
  (`test_retencion_consistency.py::test_grand_total_netted_of_retencion_is_refused`),
  contradicted operation date
  (`test_invoice_pagos_anticipados.py::test_an_advance_payment_role_with_nothing_collected_is_refused`
  and `test_the_article_25_exclusion_refuses_an_advance_payment_devengo`), and
  referentless rectificativa
  (`test_invoice_rectificativa.py::test_a_rectificativa_naming_nothing_it_corrects_is_refused`).
  Each carries a truthful companion asserting the honest invoice constructs.
- Independently mutation-proved all four underlying guards in `_models.py`
  (see Verification): each guard, disabled alone, reddens exactly the test(s)
  targeting it and nothing else, confirming each refusal is genuinely
  load-bearing for its named case rather than firing coincidentally.
- Confirmed the fifth case, over-threshold simplificada, is NOT
  representable: no field on `Invoice` records `grand_total` against the RD
  1619/2012 art. 4 simplificada-issuance ceiling (the amount threshold, a
  distinct provision from art. 6/7's content relief this model already
  implements), no such threshold constant exists anywhere in the codebase,
  and no `rd-1619-2012-art-4.html` (or any art. 4 fragment) is bundled in the
  legal corpus. Left this case out rather than testing something adjacent.

## Outcome

Four of the plan Step's five named adversarial cases were already correctly
implemented, pinned, and polarised by the prior commits; this Step's
contribution is independent verification (fresh mutation-proofs against each
guard, run and restored by this agent, not assumed from the commit message)
plus an explicit finding on the fifth. No new test file was authored: writing
one would have duplicated existing, already-correct coverage rather than
closing a real gap, which the campaign's own discipline treats as the wrong
kind of "coverage." A genuinely new file would be warranted only if a gap or
message-pinning weakness had been found; none was.

One structural finding worth recording: "falsified total" and "netted
retención" are not two independent guards -- both resolve to the SAME
totals-identity check
(`grand_total == base_total + iva_total + recargo_amount + suplido_amount`)
in `_validate_totals_and_exempt_invariants`. Mutating that one check reddens
three tests across three different narrative framings (suplido-drop,
recargo-drop, retención-netting), which is the correct, minimal design (one
identity, many ways to violate it) rather than a coverage gap.

## Verification

Baseline (all invoice tests green before any mutation):

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests/ -q --no-header -n 0
    179 passed in 5.98s

Mutation 1 -- totals-identity guard (`_validate_totals_and_exempt_invariants`,
the `grand_total != base_total + iva_total + recargo + suplido` check)
disabled:

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests/ -q --no-header -n 0
    3 failed, 176 passed in 6.22s
    (test_invoice_recargo_equivalencia.py::test_dropping_the_recargo_from_the_total_is_refused,
    test_invoice_suplido.py::test_dropping_the_suplido_from_the_total_is_refused,
    test_retencion_consistency.py::test_grand_total_netted_of_retencion_is_refused
    -- exactly the three tests targeting this one identity, nothing else)

Mutation 2 -- uncollected-payment-status guard
(`_validate_operation_date_consistency`, the
`payment_status not in _COLLECTED_PAYMENT_STATUSES` check) disabled:

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests/ -q --no-header -n 0
    3 failed, 176 passed in 6.67s
    (test_an_advance_payment_role_with_nothing_collected_is_refused[PENDING/OVERDUE/CANCELLED]
    -- exactly the three parametrised cases targeting this check)

Mutation 3 -- art-25 intra-community exclusion
(`_validate_operation_date_consistency`, the
`iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY` check inside the
`ADVANCE_PAYMENT_RECEIVED` branch) disabled:

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests/ -q --no-header -n 0
    1 failed, 178 passed in 6.28s
    (test_the_article_25_exclusion_refuses_an_advance_payment_devengo -- exactly
    the one test targeting this exclusion)

Mutation 4 -- referentless-rectificativa guard
(`_validate_invoice_class_consistency`, the
`not self.rectifies_invoice_number` check) disabled:

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests/ -q --no-header -n 0
    1 failed, 178 passed in 6.08s
    (test_a_rectificativa_naming_nothing_it_corrects_is_refused -- exactly the
    one test targeting this guard)

After each mutation, `_models.py` was restored byte-for-byte via `cp` from a
pre-mutation backup; SHA-256 matched the pre-mutation value
(`4a4907fc9e4fc4af3c7206a357d510108440899677edb781d904c3979d41c855`) after
every one of the four rounds, `git diff` against HEAD showed zero changes
every time, and the full invoice test directory returned to
`179 passed` after the final restore.

## Notes

- No production or test code changes were made. `git status` on
  `src/cadrumo/domain/invoices/` is clean at the end of this Step; only this
  exec record and the plan checkbox change.
- Over-threshold simplificada (RD 1619/2012 art. 4) is reported here as an
  explicit, deliberate gap, not silently dropped: the model has no amount
  field that could ever exceed a ceiling, and no art. 4 text is bundled to
  ground a threshold value against. Closing it would require (a) bundling
  RD 1619/2012 art. 4, (b) deciding whether the ceiling belongs on `Invoice`
  as a validated field or as an application-layer advisory (an invoice can be
  legally issued as simplificada below the ceiling and the model has no
  opinion on whether the taxpayer's *choice* to issue simplificada was
  itself lawful), and (c) sourcing the two-tier threshold (400 EUR general /
  3,000 EUR for the sector-specific exception) as a registry or
  `external_constants` value per `aeat-schema-central-config`, not a literal.
  None of that is a five-minute addition, so it was left out rather than
  covered by a test that asserts something adjacent.
