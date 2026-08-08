---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d474131f3ff142d38cfc6d1c92b72c13694f19dd8af6bd4e5c4d2f309778eade'
step_id: 'S15'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
## Description

- Establish first what the fallback did for real inputs, rather than removing it blind. Both Modelo 303 revisions declare an export layout, and an exporter-produced fichero on each of the four result dispositions reads back through that layout with 91 casillas against the fallback's five. No real input reaches the fallback on either revision.
- Replace both absorbing branches in the submitted-file casilla projection with one refusal. A layout that will not resolve and a payload that will not parse now raise a Sede parse error naming the modelo, the resolved revision, the filing year and period, the artefact digest, and the parser's own reason, which identifies the export record or literal field the read stopped on.
- Carry an instructive next step on the refusal instance rather than registering a new error code with no suggestion, so the operator is pointed at comparing the named record's declaration against what the exporter writes for that disposition.
- Add the translated message key in all four catalogues through the locales CLI, with real Spanish, Catalan and Hungarian values rather than an English echo.
- Delete the positional page-03 reader outright: the byte-offset tables including the per-year override, the fixed-width money parser, the export-reference resolver, and the fallback predicate. Drop the fallback predicate from the coverage scorer, and with it the Modelo 303 carve-out that granted full coverage to a modelo whose layout would not resolve.
- Remove the stale decimal-enrollment exemption the deleted money parser held, and drop the hardcoded entry count from the comment above that allowlist block.
- Replace the three tests that pinned the fallback with a module covering the refusal and its positive control, parametrised across both revisions and all four dispositions, and delete the synthetic single-page payload builders the old tests needed.
- Reduce the carry-history support helper to stating its five casilla values directly. It round-tripped them through the deleted positional reader purely to construct an observation, never touching the export layout a real capture reads.

## Outcome

A submitted fichero the export layout cannot read is now refused with an actionable message instead of answered with five positionally-guessed result casillas. The removal is a deletion rather than a disabled branch, so no condition can re-enable the degradation.

The two absorbing branches differed in trigger but not in consequence. One caught a layout that would not resolve, the other a payload that would not parse, and both answered with the same five guessed values carrying confidence 1.0 and a locator shaped like a byte offset. A reader could not distinguish a guessed value from a read one, which is what let the required-DID-record defect survive: for three of the four dispositions no field of a real fichero parsed at all, and every casilla an operator saw was a guess.

The coverage scorer lost its Modelo 303 exemptions in the same change. Both were unreachable once both revisions carry a layout, and each granted full extraction coverage on the strength of a failure.

## Verification

Baseline, both revisions and all four dispositions:

    uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/sede/tests/test_submitted_file_layout_refusal.py -m integration -n0 -q
    13 passed in 36.47s

The gate proved to bite, by a plugin loaded from outside the repository that rebinds the projection to absorb the refusal and answer with the positional guess:

    MUTATION APPLIED: silent positional fallback restored across 3 holders
    4 failed, 9 passed in 45.22s

The plugin asserts every name it rebinds held the original callable before the swap, so a rebinding that found no holder fails loudly rather than printing applied and passing. The four deaths are the refusal assertion and the suggestion assertion on each revision. The eight positive controls survive by design, because restoring a fallback does not change what a successful parse returns, and that survival is what separates a gate that refuses on failure from one that refuses always.

The carry-history suite whose support helper was rewritten:

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py -m "" -n0 -q
    45 passed in 41.58s

Locale parity across the four catalogues:

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok / en.yml: ok / es.yml: ok / hu.yml: ok

## Notes

The removal is complete and the fallback was not load-bearing for any real input, measured rather than assumed. It was load-bearing for four fixtures, all feeding a page-03 fragment that is not a shape a real submitted fichero takes; three were replaced by real-payload coverage and the fourth by direct construction.

Two things could not be verified and are stated rather than inferred. No bundled AEAT specimen exists for Modelo 303, so every payload here is exporter-produced and the read-back is a writer-to-reader roundtrip against our own writer; it cannot confirm that a genuine AEAT fichero matches the layout. And the refusal has been exercised on truncation, which is the same failure class as the original defect, but not on every shape the parser can refuse.

The full-tree picture at close carries unrelated peer breakage that is not this work's. A tree-wide sede and live run reported 31 failures, all at registry load or behind live-test gating, while every test in the files this change touched passed. The registry was transiently invalid mid-session from uncommitted peer edits to the IVA legal catalogue and rates, which contaminated one earlier measurement run; it recovered and the final runs above were taken green. A separate decimal-enrollment exemption for the export parser's own decimal helper is stale from a peer change and is reported, not touched.

A peer bare whole-index commit swept most of this work into the tree before it was verified, including a first version of the new test module that reddened four cases by pinning one casilla that is empty on the older revision. That version was in the tree briefly; the correction landed as its own explicit-pathspec commit.
