---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:6a01ea306a618a0ef00ff4601534a772c491b76e9ec900726878d764024ce57e'
step_id: 'S22'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Answer whether an invoice-only bucket can reach a filed M390 through the screen gap, tracing the M390 binding set to its value sources and settling whether both sides of the 390-to-303 reconciliation blocking rule derive from the same ledger, and encode the answer as a test rather than as prose

## Scope

- `src/cadrumo/application/aggregation/tests/test_modelo_bindings.py`

## Description

- Led the investigation with semantic search by meaning, then confirmed each exact site, rather than sweeping by symbol name.
- Traced M390's binding sources and the reconciliation predicate to their roots.
- Encoded the answer as three structural assertions rather than as prose.
- Corrected one assertion mid-Step when the tree proved the simpler statement false.

## Outcome

**Answer: YES — an invoice-only bucket can reach a filed M390 through the gap. `S25` is CONFIRMED as needed, not re-scoped.**

That was the live alternative this Step existed to decide: had the answer been no, adding an M390-scoped screen would have been guarding a path nobody can walk.

Three facts, together sufficient, each now asserted:

1. **The invoice-versus-ledger screen is scoped to M303** and returns immediately for every other modelo. M390 has no equivalent guard.
2. **M390 declares no invoice-sourced binding at all**, so a bucket's invoices contribute nothing to its values — there is no invoice-derived figure there that could disagree with anything.
3. **Both sides of the 390-to-303 blocking rule root in the same ledger.**

**Point 3 is the one that matters, because it is why the existing blocking rule cannot substitute for a screen.** The rule compares the ledger against itself, aggregated two ways: the annual side is a formula over ledger-sourced casillas, and the reconciliation side folds M303 totals that are themselves ledger-derived. So it catches a **period-attribution** error — a transaction booked into the wrong quarter — and cannot catch **consistent under-population**, because a transaction that was never recorded is absent from both sides equally. Zero equals zero, the rule passes, and the bucket's invoices describe operations nobody declared.

**A correction landed mid-Step.** The reconciliation figures arrive by TWO wirings, not one: a relation fold of the quarterly totals, and an annual compensation FIFO partition over the filed M303s. The first draft asserted the narrower "all relation_prefill", which the registry refuted. Both wirings still originate in filed M303 state, so the argument holds — but it now rests on the accurate statement rather than the convenient one, and the docstring was corrected with it rather than left describing a single mechanism.

## Verification

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_m390_invoice_reachability.py -q --no-header
    3 passed in 15.32s

    uv run --no-sync ruff check .../test_m390_invoice_reachability.py
    All checks passed!

The Step required the answer be encoded as a test rather than as prose, and each assertion is aimed at a fact that would change the answer if it changed: the screen gaining an M390 branch, M390 gaining an invoice-sourced binding, or the reconciliation acquiring an origin independent of the ledger.

Asserted on the registry's DECLARED sources rather than on a computed outcome, deliberately. No bucket fixture can demonstrate that a rule is INCAPABLE of detecting something — a passing calculation shows only that it did not detect it this time. The structural claim is the one that generalises.

## Notes

**Method correction taken during this Step.** Earlier Steps leaned on symbol sweeps with semantic search used only occasionally; the mandate is meaning-first, with exact search as confirmation. Driving this Step that way found the authoritative artefact immediately — a dedicated fold-in test module whose own docstring states that the ledger bindings "resolve from an empty IVA transaction ledger → zero", which is the reachability answer stated by the tree itself. A symbol sweep would have reached the same files eventually and without that sentence.

One incidental trap worth recording: a stray `rg -r` in an exploratory command silently rewrote matches instead of searching recursively, producing nonsense output. The plan warns about exactly this and it still caught me once. The output was obviously wrong rather than plausibly wrong, which is the only reason it cost nothing.
