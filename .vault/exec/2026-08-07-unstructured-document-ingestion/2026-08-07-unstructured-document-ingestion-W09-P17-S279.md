---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:49837eb096bdde51109590df2d42bb3bf53bc4d1a390c7ea3666c0da551c26c6'
step_id: 'S279'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Gate the redaction funnel against the recorded sequence outputs, since those recordings ARE operator output and running the funnel over them found a live over-redaction that every hand-authored corpus missed - no recorded sequence line may change under the funnel except where it carries a real identity - which would have caught the work-unit collision at authoring time and catches the next widening too

## Scope

- `src/cadrumo/core/tests`

## Description

- Add a standing gate asserting that no recorded operator line may change under either funnel except where the changed span is a real identity or account.
- Reuse the span-recovery instrument from the population-coverage gate: recover each hashed span from its own digest and put it to the identity, VAT-table and mod-97 authorities, rather than comparing against an authored list.
- Keep it cheap enough for the unit lane by de-duplicating lines and pre-filtering with a pattern that is a strict superset of what any shape arm can match.
- Guard the gate against its own vacuity from two directions: the corpus must still be present and large, and the sweep must still produce redactions.

## Outcome

The gate runs in the unit lane in under seven seconds over the whole recorded corpus and reports a violation as the operator line and the exact span, not as a count.

Its value is that it is not authored. Every corpus that has cleared a change to this funnel was written by the same person changing the funnel, and each was shaped so the live defect was unreachable; these recordings are captured renderings of real commands that nobody curated to spare a redaction rule. The regression it was written against would have been caught at authoring time.

The property is deliberately one-directional. It says nothing about whether redaction fires often enough, which the authored suites carry, and everything about whether it fires on operator output it has no business touching.

## Verification

    uv run --no-sync pytest src/cadrumo/core/tests/test_redaction_recorded_sequence_output.py -m unit -q -p no:randomly --durations=5
    3 passed in 13.06s
    6.61s call  test_no_recorded_operator_line_is_rewritten_unless_it_carries_an_identity

Corpus measured by the same sweep:

    files 497 | lines 725141 | changed 94 | distinct tokens 16
    correctly redacted 16 | over-redacted 0

Mutation G, restoring the shape-only arm over separators, from outside the repository:

    MUTATION G APPLIED. over-redaction restored: 'modelo-sha256:44bc266f.boe'
    2 failed, 1 passed

The failure output names the operator line rather than a tally, which is the whole point of the gate:

    redact_for_cli_output: '@result aeat --format json app modelo export --modelo 130 --year 2026 --period 1T --output ./modelo-130-2026-1T.boe' -> '... ./modelo-sha256:44bc266f.boe' (hashed ['130-2026-1T'])

## Notes

The vacuity guards are the load-bearing half. A gate asserting an absence over a corpus that moved reads identically to a gate over a clean corpus, so the file-count floor and the redactions floor both have to fail rather than pass when the corpus is not there.

The pre-filter exists only for runtime and is a strict superset of what the patterns can match, so it cannot hide a violation. If a future arm matches something the filter does not admit, the filter must widen with it.
