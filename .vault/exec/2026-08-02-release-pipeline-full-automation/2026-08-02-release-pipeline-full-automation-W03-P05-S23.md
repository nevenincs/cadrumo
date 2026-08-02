---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:62643f6ce3222b21a34b2bdec01563559daab9842c6c89f34837c55bea3109fe'
step_id: 'S23'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Wire the packaging campaign stage to dispatch packaging-smoke at the bumped commit and resolve its own run through the run-resolution module rather than the newest run, then wait on the conclusion waiter, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the stage invokes dev.release.run_resolution and never reads a bare latest-run query, with end-to-end chaining flagged non-local and CI-only

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/release/tests/test_release_orchestrator_workflow.py`
- `dev/release/run_resolution.py` (same scope deviation as S22, reasoned in that record)

## Description

- Add `main()` to `dev.release.run_resolution`, composing dispatch, identity resolution, and conclusion waiting, and exiting non-zero on any conclusion other than success.
- Wire the `campaign` job, keyed on the bump's output commit, with an `always()` guard so a skipped bump on the resume path does not skip the campaign.
- Add the resume short-circuit reading the supplied run's head commit instead of dispatching.
- Add two conformance tests.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q` reports 11 passed, `test_run_resolution.py` still 26 passed, and `dev/ci/tests` 14 passed. My addition introduced no new lint findings; the two remaining in that module (`D105`, `UP047`) are the pre-existing peer-lane ones I attributed during P04.

End-to-end chaining is CI-only and unexercised: nothing has dispatched a real campaign from this workflow.

## Notes

The recency-shortcut assertion is the one worth keeping. It scans the stage for the ways a bare newest-run query gets written - `--limit 1`, `per_page=1`, `| head -1`, `[0].id` - rather than only asserting the module is invoked, because the failure it guards is not "the resolver is missing" but "someone added a quick lookup beside it". That failure is invisible in every downstream check: `packaging-smoke` queues rather than cancels, so the newest run can belong to a neighbouring campaign, and its cohort is internally consistent and hash-verifiable - just not this release's. Every gate downstream would pass on the wrong bytes.

The `always()` guard on the campaign job is load-bearing and easy to get wrong. The bump job is SKIPPED on a resume, and a skipped dependency skips its dependents by default, so without `always()` the entire resume path would silently do nothing and report success. The condition still refuses a genuinely FAILED bump, so the guard distinguishes "skipped deliberately" from "failed", which a bare `always()` would not.

The exit code matters as much as the resolution: `main` returns non-zero for any conclusion other than success, so a red campaign stops the chain rather than letting it seal a candidate over a failed build.
