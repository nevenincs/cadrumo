---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:3129201bd039be5f50d0a52e7d8ca4da2c21625dd3be352e8d04800177ea33d9'
step_id: 'S24'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Extend the screen past its four-cuota screened binding set to cover recargo de equivalencia, proving a recargo figure diverging from the ledger is caught

## Scope

- `src/cadrumo/application/aggregation/_modelo_bindings.py`

## Description

- Ran the canonicalisation sweep first: searched by meaning for how a recargo reaches an IVA observation, before touching the screened set.
- Found the canonical mechanism already exists and the invoice adapter simply does not populate it.
- Extended the single canonical bridge rather than constructing observations at the screen.
- Added the three recargo tier bindings to the screened set.
- Made an ambiguous tier attribution skip rather than guess, and asserted that directly.

## Outcome

**The screen now covers the recargo de equivalencia tiers.** A supplier to a recargo-regime retailer charges it ON TOP of the cuota (LIVA art. 161), so an invoice carrying one against a ledger missing it under-declares by exactly the surcharge — real money owed, not a presentation detail.

**Extending the binding set alone would have been vacuous, and finding that out first is the substance of this Step.** The screen builds its observations from LINE metadata, while an invoice's recargo is an invoice-level field. Adding the three bindings without carrying the surcharge onto the observation would have compared zero against zero, never fired, and passed as a completed Step — the vacuous-green shape this plan was rewritten to eliminate, arriving this time as a plausible one-line change.

**The canonicalisation sweep decided how to fix it, not just where.** Searching by meaning for how a recargo reaches an observation showed the mechanism already exists and is canonical: `IvaLedgerObservation.recargo_amount`, routed to the M303 recargo casillas by the `recargo_amount_sum` fact, populated on the ledger path from the transaction's own field. The gap was only that the invoice adapter — which its own docstring calls "the canonical ledger to modelo bridge" — did not carry it.

So the surcharge is carried through **that bridge**, extended with an optional parameter, rather than by having the screen build observations itself. A second construction site for the same concept would be free to drift from the bridge's classification rules, and would have been invisible to anyone reading either site alone. The parameter is on the function rather than something a caller sets on the returned record, for the same reason.

**Ambiguous attribution is skipped, not guessed.** The recargo is recorded once per invoice while the casillas are per rate TIER, so an invoice spanning several tiers cannot say how the surcharge divides. Placing a real amount in the wrong casilla is worse than leaving it unscreened: a mis-tiered recargo is a wrong figure declared confidently, where an unscreened one is only unscreened. That limit belongs to the invoice-level field, not to this screen, and it is asserted directly rather than left implicit.

## Verification

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py -q --no-header
    20 passed in 23.14s

    uv run --no-sync pytest src/cadrumo/application/aggregation src/cadrumo/domain/iva src/cadrumo/application/modelo -q --no-header
    2530 passed in 122.91s (0:02:02)

    uv run --no-sync ruff check src/cadrumo/application/aggregation/ src/cadrumo/domain/iva/
    All checks passed!

The refusal proof asserts the recargo tier is named in the refusal's per-binding excess map, so the operator is told WHICH figure is missing rather than only that something is. The ambiguity proof asserts the attribution helper directly, because the outcome it guards — a surcharge landing in the wrong tier — would otherwise be invisible in an end-to-end assertion that only checks whether the screen fired.

## Notes

**Method note, following the standing directive to use semantic search extensively for canonicalisation and dedup.** Leading with a meaning-based search rather than a symbol sweep changed the shape of this Step twice: it revealed that the observation field and its routing fact already existed (so nothing new had to be designed), and it identified the adapter as the declared single bridge (so the fix belonged there rather than at the call site). A symbol sweep for `recargo` would have found the same files and supported neither decision — it would have shown where the word appears, not where the concept is owned.

One commit-mechanics note: the first attempt placed `-F -` after the `--` separator, so git read it as a pathspec and committed nothing. Caught immediately by checking the resulting log rather than trusting the command's silence.
