---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:92bd5adb99dfc586abd424fb9f86fe989e93709e26367a7b5f7918a251f8a911'
step_id: 'S18'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Make promotion idempotent by marking a candidate consumed once its publication dispatch succeeds and refusing a second promotion of the same cohort id, backed by the unchanged version-identity authority which refuses an owned version regardless, so a promoter tick overlapping its predecessor cannot double-publish, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q passes with a case running two promoter passes over one elapsed candidate and asserting exactly one dispatch

## Scope

- `dev/release/soak_promoter.py`
- `dev/release/release_candidate.py`
- `dev/release/tests/test_soak_promoter.py`

## Description

- Add `consumed_tag` and `mark_candidate_consumed`, retagging a promoted candidate out of the selectable namespace.
- Add the optional `consume` action to `promote_once`, invoked strictly after the dispatch returns.
- Add three tests: two overlapping ticks dispatching exactly once, a failing dispatch leaving the candidate selectable, and the consumed tag falling outside the selectable namespace while remaining a real record.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_soak_promoter.py dev/release/tests/test_release_candidate.py -q` reports 28 passed. Lint, format, and `ty check` clean over my files.

## Notes

Two orderings were available and only one is recoverable, which is what decided the design.

Consuming BEFORE dispatch makes the failure mode a stranded cohort: the candidate is retired out of the selectable namespace, the dispatch then fails, and no later tick can ever select it again. That release silently never happens, and the absence is indistinguishable from nobody having started one - the same invisible failure the GC hazard in S14 produces. Consuming AFTER dispatch makes the failure mode a possible re-dispatch, which the unchanged version-identity authority refuses outright for an owned version, and which the publication path converges on per destination in any case. The test asserts this directly with a dispatch that raises, confirming the candidate survives for a later tick.

Consumption RETAGS rather than deletes. Deleting buys the same idempotence, but it destroys the record naming which runs produced a published version - precisely the evidence a later audit wants, and precisely at the moment it becomes worth having. The consumed namespace deliberately fails `CANDIDATE_TAG_RE`, so selection ignores it structurally rather than by a status field someone must remember to check; the test asserts both halves, that the retag leaves the selectable namespace and that the record still parses as a real release entry.

The idempotence test drives two real ticks against a mutable forge list rather than asserting on a call count, so what it observes is the same thing production observes: the candidate is gone from the selectable set, therefore the second tick has nothing to select.
