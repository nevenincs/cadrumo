---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:5b21471b9548526be84ce0dafed0997789a64589ac5540fe5370b2bd59c6e5d2'
step_id: 'S25'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Add an M390-scoped equivalent of the invoice-versus-ledger screen, because the 390-to-303 blocking rule compares two ledger-derived sides and cannot detect consistent under-population, proving a bucket whose invoices exceed its ledger is caught on the annual path

## Scope

- `src/cadrumo/application/aggregation/_modelo_bindings.py`

## Description

- Ran a fragmentation sweep by meaning over the invoice-versus-ledger gate surface BEFORE writing anything, per the standing directive.
- Compared M390's declared bindings against M303's, which decided the implementation shape.
- Generalised the existing screen to a per-modelo binding table instead of adding a second screen.
- Added a drift guard asserting the two entries cover the same concepts.
- Updated the earlier reachability encoding, which reddened when the gap closed.

## Outcome

**M390 is screened, and it is screened by the SAME screen rather than a second one.** That choice is the substance of this Step, and it came from the fragmentation sweep rather than from the Step text, which asks for "an M390-scoped equivalent" — wording that reads as a new function.

M390 declares the same seven cuota concepts M303 does under its own id prefix. A parallel function would therefore have been **two implementations of one comparison**, free to drift, and a widening applied to one and not the other is invisible until a filing is wrong. That is not hypothetical: it is exactly how the ES-only counterparty filter and the missing recargo tiers survived on the M303 side long enough to need their own Steps. Adding a second screen would have reproduced the same failure mode by construction, on the day it was written.

A drift guard now asserts the two table entries cover the same concepts with the modelo prefix stripped, so divergence fails a test rather than surfacing as a wrong return.

**Why M390 needs this more than M303, not less.** Its 390-to-303 reconciliation BLOCKING_RULE compares two figures that both root in the same ledger, so it detects a transaction booked into the wrong quarter and cannot detect one that was never recorded: both sides are equally short and the rule passes. The earlier Step established that; this one closes it.

**The earlier encoding reddened when this landed, and that is the system working.** Its first assertion stated the screen skipped M390. The fact changed, so the test failed rather than quietly staying green. It now pins the inverse — that M390 has a screened-binding ENTRY — asserted against the table rather than by calling the screen, because a screen that ran against an empty binding set would pass a call and guard nothing.

## Verification

    uv run --no-sync pytest src/cadrumo/application/aggregation src/cadrumo/application/modelo src/cadrumo/domain/iva -q --no-header
    2530 passed in 116.89s (0:01:56)

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_m390_invoice_reachability.py -q --no-header
    4 passed in 19.87s

    uv run --no-sync ruff check src/cadrumo/application/aggregation/
    All checks passed!

**One failure appeared and was diagnosed rather than absorbed.** A deductible-evidence gate test failed once in a parallel package run. It passed in isolation, passed with the whole module run sequentially, and did not reproduce on a second full package run (1541 passed). That is the documented parallel/loader-cache flake signature for this suite, not a regression from the widening — recorded rather than silently re-run until green, because "it passed the second time" is only evidence if the first failure was actually explained.

## Notes

**The fragmentation sweep also cleared a false positive, which is worth recording as much as the true one.** Searching by meaning for invoice-versus-ledger consistency gates returned five modules — the screen, a deductible-evidence gate, an export-evidence gate, a ledger-drift gate, and an M200 required-input gate. They look like a fragmented family. They are not: each guards a different question at a different lifecycle point (value comparison, evidence presence, export evidence, staleness, missing manual input), and collapsing them would merge unrelated concerns.

The directive to treat fragmentation as a criticality does not mean treating adjacency as fragmentation. The discriminator used here was whether two sites answer the SAME question — which the M303 and M390 screens would have, and these five do not.

`P05` is complete with this Step, and every one of its four Steps changed shape from what the plan specified: the reachability question resolved yes rather than re-scoping the phase, the country filter turned out to be a proxy rather than a scope limit, the recargo extension would have been vacuous without carrying the field first, and this Step became a generalisation rather than an addition.
