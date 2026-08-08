---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b5b51370f2f5534d27e3752995690e1afc1cc8a1abe4b4a6786c126f0b134cd6'
step_id: 'S164'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

- `src/cadrumo/llm`
- `src/cadrumo/application/ledger`

## Description

- Add a co-location module owning the party-region partition, the containment decision and the contradiction findings.
- Extend the anchor module with a region-scoped printed-token search, and re-express the whole-document one on it so there is still one authority for what counts as printed.
- Promote the party table to a public accessor so the resolver partitions over exactly the sides the stamp enrols.
- Let the stamping pass accept document-established attribution alongside origin-established attribution, the two composing rather than overriding.
- Resolve co-location inside the single grounding entry point, before the stamp rather than after it.
- Add a discrepancy kind for a contradicted attribution and map it to the undetermined-establishment block reason.
- Gate the transposition fixture, the retiring absence assertion, and the prompt-does-not-grow property.

## Outcome

Segmentation is by LINE, and that was measured rather than assumed. Every text-layer transcription in the evidence corpus carries ZERO blank lines: a PDF extractor emits reading-order lines and the visual gap between two address blocks leaves no character behind. A blank-line-delimited implementation would have read as the obvious one, passed a fixture written to match it, and never fired on a single real document — the same failure as evidence no resolver consumes, in mirror image. The fixtures here are shaped like the measured corpus for exactly that reason.

Three outcomes, and the third carries the design. A value inside its own party's region and not the other's is attributed and the interim stamp is cleared. A value only inside the other party's region is contradicted. Everything else stays unresolved and keeps the stamp: no usable heading, a value printed on both sides, a value printed on neither. The both-sides case is not hypothetical — the bundled zugferd specimen reprints the supplier's postal code in a remarks block below the customer heading, so reading presence in its own region as sufficient would let any repeated figure launder itself into an attributed one.

A contradiction is REPORTED, never corrected. Moving the value into the region containing it would replace the reader's unverified assignment with the resolver's, and both rest on one reading of one document; the blocks may have been swapped or the value may have been printed in the wrong place, and the page does not settle which. It blocks, which is right here and only here: it fires on positive evidence of a swap, never on a document the layout simply cannot separate, so the ordinary case is not refused.

One heading is treated as no partition at all. With a single anchor every value on the page falls inside its region by construction, which would attribute the other party's values to it — a bug that would have looked like the feature working.

The retiring assertion the amendment mandates is in place: a co-located value carries no interim stamp. The interim and its replacement cannot ship side by side, which is what the ADR author named as the cleanup that always gets forgotten.

The prompt does not grow. Role evidence stays on the two identity fields, and the gate asserts that as a PROPERTY — every role-evidence-bearing field is a party identity field and no attributed address field carries one — rather than as a pinned count, which would have to be edited whichever way the set moved.

## Verification

    uv run --no-sync pytest <the four owned test modules> -n0 -q -m unit
    39 passed in 3.70s

    uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/core/tests src/cadrumo/llm/tests -n0 -q -m unit --deselect <peer-red module>
    8 failed, 2321 passed, 59 deselected, 16 warnings in 370.51s (0:06:10)

Mutation M3, the resolver neutralised on the CONSUMER's namespace, three rungs:

    2 failed, 10 passed in 3.48s
    invocations: 10, invocations_that_changed_state: 8

Mutation M4, the containment decision forced to always attribute:

    4 failed, 8 passed in 2.69s
    invocations: 24, invocations_that_changed_state: 11

The two probes red disjoint sets and that is the point: M3 reaches only the wired path, so it reds the stamp-clearing and the blocking refusal; M4 reaches the decision itself, so it reds the transposition gate. Neither alone would have proven both halves.

## Notes

The state rung, not the invocation count, is what the ladder buys. Both probes wrap the real callable, record what it would have returned, and compare that against what the patched one returns — so the recorded figure is not "the patch ran" but "the patch ran AND changed the answer", which are different claims and only the second simulates a defect.

All eight unit-lane failures are owned elsewhere and none names a file this change touched: the preflight families belong to the identification-axis lane, and the two core gates report combined period strings and route literals in adapter, live and registry test files. Verified by grepping the failure output for this change's own module names, which returns nothing.

One intended file is absent from this change's commit. The discrepancy kind had already been swept into HEAD by another lane's whole-index commit before the commit ran, so its diff was empty by then; the member is present at HEAD and the mapping that consumes it is in this commit.
