---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:abc0139543e6579586d061a116f6bfd4547b1b712f65335d669edf0b3e5f43e0'
step_id: 'S17'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Require the promoter to re-run the readiness gate against the sealed cohort and its bound evidence rows immediately before dispatching, so a candidate whose blocking evidence regressed during its window is invalidated with a named refusal instead of promoted on a stale green, honouring the soak policy that a blocking regression invalidates a cohort and is never repaired in place, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q passes with a case that reds the readiness report for an elapsed candidate and asserts no dispatch is attempted

## Scope

- `dev/release/soak_promoter.py`
- `dev/release/tests/test_soak_promoter.py`

## Description

- Add `promote_once`, running one tick as select, then re-verify, then dispatch, with the readiness evaluator and the dispatch action both injected.
- Refuse an elapsed candidate whose readiness report carries blocking failures, naming each failing check and its detail in the refusal.
- Order the clock check before the gate so readiness is never consulted for a candidate that cannot promote.
- Add three tests: the regression refusal with a no-dispatch assertion, a clean-promotion positive control, and the ordering assertion.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_soak_promoter.py -q` reports 9 passed. Lint and `ty check` are clean over my files.

## Notes

The re-verification is the reason the soak has any teeth at promotion time. The gate that ran at seal time proved the cohort sound two or three days earlier, and "sound then" is not "sound now" - that gap is precisely what the soak window exists to observe. Promoting on the seal-time green would make the window a delay rather than a check.

The refusal asserts `dispatched == []` rather than only asserting the decision. A promoter that dispatched and then reported a refusal would satisfy a decision-only assertion while having already published, which is the failure the ordering exists to prevent; the observable is what was dispatched, so that is what the test observes.

The clean-promotion test is a positive control for the refusal, not decoration. Without it, a `promote_once` that never dispatched anything under any circumstances would pass the regression test perfectly.

## Blocked / attributed

`ruff check dev/release/` (directory-wide) currently reports 19 errors - 18 D103 and 1 UP047 - entirely in `dev/release/run_resolution.py` and `dev/release/tests/test_run_resolution.py`, committed by the parallel P02 lane in `9ad9e0c593`. None are in the six files this Phase owns, which pass clean when checked explicitly. Recorded and attributed rather than absorbed: those files belong to an actively-running peer Step, and editing them mid-flight would collide with in-progress work.

One process correction for my own later Steps. I ran `ruff check --fix` across the whole `dev/release/` directory, which in a shared worktree can rewrite a peer's files. It did not here - `git status` confirms only my two files changed, and the peer's remaining findings are unfixable ones - but the safe habit is to scope every `--fix` to the explicit files I authored, which is what the remaining Steps do.
