---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:76f2f751f99a1c278e2f050ae5fcf422e1a90effaf4178aeef2ab6644da52b09'
step_id: 'S229'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec W09.P17.S229

## Scope

- `src/cadrumo/application/ledger`

## Description

- Search semantically for the attribution stamp and its advisory before writing anything, then read both modules' prose against the measurement.
- Correct the two docstring claims the measurement falsifies, at the module that makes them and at the module that inherits them.
- State the cause at the region builder where the drop actually happens, rather than only at the package's front door.
- Retire the word "interim" from the resolver's prose, since it asserts a succession that did not occur.
- Make the honest state executable: the real layout resolves nothing, the designed layout still does, and the stamp with its advisory survives the real one.
- Give the layout assertion the repository's asserted-gap prefix, because it should fail the day the geometry lands.
- Mutation-prove all three, and correct one of my own docstrings when the proof showed its claim was too strong.

## Outcome

The ruling was the cheap reading, and the deliverable is legibility rather than behaviour: no production logic changed. What changed is that the code now says what is true.

Two prose claims were falsified by the measurement and both read as reassurance. The resolver's own docstring opened by calling itself "the structural answer to party attribution, replacing the interim stamp for every document whose layout can carry it" — and no document's layout carries it. The stamp's module opened with "This module is the honest interim, not the fix", describing a successor that had already shipped and does not fire, so a reader met a module apologising for being temporary while it was in fact the operating control. Neither was wrong when written. Both became wrong when the successor landed and turned out not to work, which is the failure mode where prose describing a state as transitional is falsified by the transition happening.

Both now carry the measurement: the ceiling, that it is a ceiling rather than a rate because authored anchors bound every real reader, and the cause. The cause is also stated at the region builder itself, because that is where the zero-width span is dropped and a reader tracing the behaviour arrives there rather than at the module docstring. That drop is still correct — keeping the span would attribute one party's values to the other, the exact transposition the module exists to refuse — so the finding is about the primitive being wrong for the layout, never about the guard being wrong.

The word "interim" is gone from the resolver's prose, replaced by naming the stamp for what it does. It was the load-bearing word: it told every reader the situation was temporary, and a lane reading it would have inferred the successor was pending rather than shipped and inert.

Three assertions carry the state. The real layout resolves nothing. The designed layout still partitions, which is what separates "the resolver cannot fire on real documents" from "the resolver is unwired" — two findings calling for opposite responses, one a pipeline question and one a bug here. And on the real layout the stamp survives and the operator still gets the advisory, which is the claim that the control is real rather than nominal.

The layout assertion carries the repository's `test_asserted_gap_` prefix. It is expected to fail the day the region builder learns to split a shared line or the pipeline preserves the geometry, and that failure is the notification to replace it and update the prose. Without the prefix a triager reads the name at speed, takes it for a contract, and relaxes it to match the code — cancelling the gate at the moment it fires.

## Verification

    COLOCMUT_MODE=keepzero      -- the region builder keeps zero-width spans
    spans (stacked, two-column) (2, 1) -> (2, 2)
    FAILED test_asserted_gap_a_two_column_header_resolves_nothing
    FAILED test_a_two_column_document_keeps_the_stamp_and_the_operator_keeps_the_advisory
    2 failed, 13 passed

    COLOCMUT_MODE=nopartition   -- the region builder never partitions
    spans (stacked, two-column) (2, 1) -> (0, 0)
    FAILED test_the_stacked_header_still_partitions_so_the_zero_is_about_layout  (+6 pre-existing)
    7 failed, 8 passed

    COLOCMUT_MODE=clearstamp    -- an unsegmentable document gets a clean bill
    FAILED test_a_two_column_document_keeps_the_stamp_and_the_operator_keeps_the_advisory  (+2 pre-existing)
    3 failed, 12 passed

The first mode is the naive fix a later reader would reach for, and the asserted-gap test notices it, which is the notification working rather than a regression. The second reds the positive control, so a resolver that stopped working could not hide behind a finding that says it does not fire. The third is the silent removal of the only control a prose document has.

**One of my own docstrings was wrong and the proof is what showed it.** The stamp test claimed a clean-bill change "would pass every attribution test above", and the mutation reds two neighbours as well, so the claim was too strong. Corrected to the accurate one: those two reach an empty resolution by removing role evidence or by transposing values, both constructed shapes, while this reaches it through the header real invoices actually print — the layout is what this adds, not the stamp surviving in isolation.

**The first `clearstamp` attempt was aimed at the wrong function and produced a false negative.** It patched the resolution's per-field accessor, and the stamping path never calls it: the attributed set is built from the outcome mapping directly. The gate reported green while the defect it exists for was simulated, which is the shape that reads as "the gate does not catch this" and is the inverse of the truth. Re-aimed at the stamping function, it reds.

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_party_colocation.py -n0 -q
    15 passed in 3.03s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests -n0 -q
    1224 tests ran; 26 deselected
    1224 passed, 26 deselected, 16 warnings in 203.07s

    uv run --no-sync ruff check src/cadrumo/application/ledger/   All checks passed!
    uv run --no-sync ty check <the three changed files>           All checks passed!

## Notes

No production logic changed. The row asked for a decision to be made legible, not for the resolver to be altered, and altering it would have pre-empted the sizing row that owns the other half.

`ty` reports 19 diagnostics across the ledger package, none in the three files changed here. They sit in the classification-assembly and party-fact modules belonging to another lane's active work, and are not absorbed.

The reading is HEAD for the three changed files, which were clean before the change and committed under this Step's own explicit pathspec. The wider ledger suite reading was taken with another lane's uncommitted work present in neighbouring modules.

The unit lane only.
