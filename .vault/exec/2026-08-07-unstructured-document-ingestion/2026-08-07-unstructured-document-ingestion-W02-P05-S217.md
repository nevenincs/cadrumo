---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d2ce1b40ec0f60e13e072b6fabf15b32b6ce0c83edbda81da75ddc03f55955aa'
step_id: 'S217'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Pin the sidecar part-infix regex to its producer

## Scope

- `dev/docs/preprocess`

## Description

- Assert the gate's part-infix strip against the producer's own output for a synthetic three-part source, so a change to the naming scheme reds the consumer that depends on it.
- Assert, before the strip, that the producer emitted a name distinguishable from the source, because a producer that stopped infixing satisfies the strip trivially.
- Assert the single-part case separately: the producer names it directly from the source, and the strip must leave a legitimate filename alone.

## Outcome

A convention observed in two places is now a contract. The corpus is entirely single-part, so no committed sidecar exercised the branch and nothing in the tree would have reddened had the extractor changed its part naming.

The non-vacuity assertion turned out to be the load-bearing half rather than a garnish. Measured directly: under a producer that stops distinguishing parts, the strip assertion alone passes, because stripping nothing from an unchanged name also yields the source name. That is the second of the two failures the row names, and the strip cannot see it.

## Verification

    uv run --no-sync pytest dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py -n0 -q -m "unit and docs"
    11 passed in 5.19s

Proved to bite against three producer changes, each reporting how many times the substituted producer was called so an ineffective rebinding could not read as a pass:

    [MUT new infix scheme  ]: producer called 1x -> REDS
    [MUT no infix at all   ]: producer called 1x -> REDS
    [MUT prefix not suffix ]: producer called 1x -> REDS
    [CONTROL real producer ]: -> PASSED

The prefix arm is worth keeping: the regex is anchored at the end, so a producer that moved the infix to the front would leave the gate stripping nothing.

## Notes

Not a defect and the predicate was correct, so this is a hardening rather than a repair.
