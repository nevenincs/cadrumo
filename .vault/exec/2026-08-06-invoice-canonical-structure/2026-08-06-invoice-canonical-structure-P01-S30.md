---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:dc3b38e3be8e3aa96fd7b0b8494a506d85d14ea6446bb0411c1a36b17f3c1874'
step_id: 'S30'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Add the parameters that make the canonical writer reach parity with what the canonical model already claims to represent, namely invoice-class, series, rectifies-invoice-number and recargo-amount, which no production path can set today so every canonically written invoice is ORDINARIA with no series and no recargo by construction and rectificativas are unrepresentable

## Scope

- `src/cadrumo/application/invoices/_creation.py`

## Description

- Added the four missing axes to the canonical builder and threaded them through the persisting service.
- Entered the recargo into the totals identity, leaving the retención outside it.
- Added the rectificativa persistence proof, a refusal proof, and a positive control on the default path.
- Corrected one test to state the invariant that actually fired rather than the one it was drafted against.

## Outcome

**One of the two rows the conservation inventory ruled blocking is now closed.**

The canonical aggregate has always modelled invoice class, series, the rectified invoice number and the recargo, and no write path could set any of them. Every canonically-written invoice was therefore ORDINARIA with no series and no recargo **by construction**, and a rectificativa was unrepresentable. The aggregate claimed a vocabulary the writer could not speak, and folding the operator surface onto it in that state would have been a capability loss on its face — not a subtle one.

The recargo enters the totals identity and the retención does not, because the recargo de equivalencia rides INSIDE the invoice total while a withholding is settled outside it. The model re-checks that identity exactly, so a recargo the lines do not support refuses rather than being balanced silently.

**The refusal proof landed on a sharper invariant than it was drafted against, and the test was corrected to match the tree rather than the tree to match the test.** The draft asserted a totals mismatch; what actually fired was the rule that a recargo must be zero when every line is exempt — because the recargo is charged on the cuota of a taxable supply, and a supply exempt by law bears no cuota and therefore no recargo.

That is the better proof, and it is the reason the parameter is safe to expose at all: the writer does not merely add the figure into a total, it hands it to invariants that already know when a recargo is legally impossible. A writer parameter that only summed would have accepted a surcharge on an exempt supply and declared it.

The change is additive, and a positive control pins that the default path still produces an ordinary invoice with no series and no recargo, since every existing caller omits all four axes.

## Verification

    uv run --no-sync pytest .../test_creation.py .../test_fold_record_classes.py -n 0 -q --no-header
    31 passed in 7.31s

    uv run --no-sync ruff check .../_creation.py .../test_creation.py
    All checks passed!

The rectificativa proof persists through the real encrypted repository and reloads, because the claim is that all four axes SURVIVE the boundary rather than that the builder accepted them.

The RED that corrected the refusal test is quoted, since it names a different invariant from the one drafted:

    Value error, recargo_amount must be zero when every line is EXEMPT or NOT_SUBJECT

## Notes

The CLI options for these four axes are NOT added here. That is `P02.S05`'s scope, and this Step deliberately stops at the application boundary: the aggregate can now hold what it models and the writer can set it, which is what the conservation gate required. Exposing the operator flags is a separate change with its own locale and documented-command obligations.

One blocking row remains open on the conservation inventory: the canonical write paths still emit no bucket lifecycle events. `P03` stays shut until that closes.
