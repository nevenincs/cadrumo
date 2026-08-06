---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:b2b54df898dbc5fd3c6490f0afddd1d6210ffcc52aafa4f55ddadadd3a446d9b'
step_id: 'S39'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Let a general-regime row carry its art. 75 devengo date, so IVA stops being attributed to the bank movement date for the one regime whose law binds it to the operation date

## Scope

- `src/cadrumo/domain/transactions/_models.py`
- `src/cadrumo/domain/transactions/_dates.py`
- `src/cadrumo/application/aggregation/_iva_ledger.py`

## Description

- Rename `cash_accounting_operation_date` to `operation_date` across its six sites and restate it as the LIVA art. 75 devengo date rather than a criterio-de-caja informational field.
- Drop the regime gate that refused the date whenever `cash_accounting_treatment` was `NONE`, keeping the requirement that a criterio-de-caja row carries one.
- Keep the settlement-evidence collection series regime-gated, since only that regime settles one cuota across several collections.
- Reach the devengo date in the eligible-date span so the period partition stops dropping the row, while keeping the art. 163 *quinquiesdecies* year-end fallback out of a general-regime span.

## Outcome

Landed as commit `8a783e869e` (7 files, +246 / -33).

The defect was measured on the real aggregation path before any edit, and the same scenario re-measured after. An invoice issued 2026-02-10 (1T) and paid 2026-08-20 (3T), general regime:

```
BEFORE  1T: 0 observations              3T: cuota 210.00
        and the operation date was REFUSED at construction

AFTER   without an operation date       3T: cuota 210.00   (unchanged)
        with the art. 75 date recorded  1T: cuota 210.00
        eligible span (2026-02-10, 2026-08-20)
```

The change is opt-in by construction. Every row recorded before it carries no operation date, so no existing attribution moves; what changed is that the legally-controlling date became expressible at all.

## Verification

```
uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_general_regime_devengo_date.py -n 0 -q --no-header
6 passed in 3.12s
```

```
uv run --no-sync pytest src/cadrumo/domain/transactions src/cadrumo/application/aggregation
  src/cadrumo/adapters/persistence/profile src/cadrumo/domain/invoices src/cadrumo/domain/iva
  -n 0 -q --no-header
1391 passed, 7 deselected in 60.38s (0:01:00)
```

Lint and format clean over every touched file.

Three mutations, each applied to a copy-aside and restored: restoring the regime gate on the operation date reddens 4, dropping the operation date from the eligible span reddens 1, and leaking the criterio-de-caja year-end fallback onto every regime reddens 1. Both sources restored byte-exact, verified by SHA-256 match.

## Notes

**The legal question was researched before the design was fixed, and it overturned the working assumption.** The first instinct was to populate the devengo date from the linked invoice's issue date. Bundled LIVA art. 75.Uno does not mention the invoice date at all: devengo is when the goods are placed at the acquirer's disposal, or when the service is rendered. AEAT states the same and adds that a business-to-business invoice may be issued up to the 15th of the month following, and "deberá declararse en el periodo en que se ha producido el devengo de la operación o el pago anticipado". An operation on 25 June invoiced 10 July therefore belongs to the second quarter, so deriving the devengo from the issue date would be wrong across exactly the month and quarter boundaries where attribution changes.

Several widely-read secondary sources state the opposite outright, that the tax is devengado when the invoice is issued. That is the failure mode the grounding discipline exists to catch: the paraphrase is usually true and legally wrong, and the bundled article settles it in one read.

The conclusion is what justifies the shape of this Step. No derivable proxy is authoritative, so the devengo date has to be a recorded fact rather than something inferred, and the field had to become available to the general regime rather than a fallback chain being built behind it.

**Art. 75.Dos was the other reason not to invert the default.** Where the price is collected before the hecho imponible, devengo moves to collection for the amount actually received. So the payment date is not merely a bad proxy that should be replaced everywhere: for a pago anticipado it IS the devengo date. A change that made the operation date universally authoritative would have broken that case. Prepayments are not representable at all today, which is recorded as a separate finding.

**The span change is easy to get wrong in the safe-looking direction.** The date module documents its span as a deliberately conservative superset, resolving the asymmetry in favour of over-selection because under-selection is a silent under-declaration. That argument justifies reaching the devengo date; it does not justify keeping the criterio-de-caja year-end fallback on a general-regime row, which would select the row into quarters it can never file in. One mutation covers each direction.

**A test asserts the cuota is declared exactly once across the whole year.** Widening the span means the period partition now selects the row from either end, and the aggregator's own date gate is the only thing choosing a single quarter. A per-quarter assertion would still pass if that gate stopped discriminating and the row declared twice; the year-total assertion is what catches the over-declaration.

**The commit was blocked for roughly half an hour by a stale `.git/index.lock`.** Diagnosed rather than removed: the lock was 28 minutes old, no commit had landed after its mtime, and no git process was running, which together read as residue from a crashed process rather than live contention. Removing anything under `.git/` is categorically outside an agent's remit here regardless of that confidence, so the work was held complete-but-uncommitted and the operator cleared it.
