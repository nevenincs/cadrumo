---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:15aac1a73f13d463a5d50e80661501cd45a4664adef3011e9fd4de2c0cd475a3'
step_id: 'S30'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Attach an always-on failure-alert step to the orchestrator, the soak promoter, the publication authority, and the docs publisher, because the click was the only moment a human was structurally guaranteed to look and a silently failed chain is indistinguishable from a release nobody started, gate: uv run --no-sync pytest dev/release/tests/test_release_alerting.py -q passes asserting each of the four workflows carries an if-failure alert step invoking the emitter

## Scope

- `.github/workflows/release-orchestrator.yml`
- `.github/workflows/release-soak-promoter.yml`
- `.github/workflows/publish-release.yml`
- `.github/workflows/docs-publish.yml`

## Description

- Add a dedicated failure-only `alert` JOB to the orchestrator and the publication authority, each needing every other job in its workflow.
- Add a failure-guarded alert STEP to the single-job soak promoter.
- Upgrade the docs publisher's existing failure step so it reaches the operator rather than only annotating the run log.
- Add three conformance tests, and narrow two earlier assertions this Step legitimately falsified.

## Outcome

425 passed across `dev/release/tests`, `dev/deploy/tests`, and `dev/ci/tests`.

## Notes

### The shape mistake I made and caught

My first pass appended the alert as a STEP to the end of each workflow, which for a multi-job workflow lands it in the last job. That is almost entirely useless and looks completely correct: `if: failure()` inside a job fires only when a step in THAT job failed, and a job whose dependency failed never runs at all. So a bump failure, a campaign failure, an acquisition failure - every failure except one in the final stage - would have alerted nobody, while the workflow visibly carried an alert step and the suite stayed green.

The fix is a dedicated job needing every other job, gated on `failure()`. The conformance test now asserts the alert job's `needs` equals every other job in the workflow, so adding a stage without extending that list reds rather than silently dropping out of coverage. The single-job promoter keeps a step, which is correct there because it has no earlier job to be skipped by, and a test pins that distinction rather than leaving it to look like an inconsistency.

### The docs publisher was already claiming to alert

`docs-publish.yml` carried a step named "Alert on failure without touching the release" whose entire body was `echo "::error::"`. A workflow annotation is visible only to someone already reading the run - which is exactly the person the removed approval click used to summon, and no longer does. The name and the module docstring both asserted alerting; the code delivered a log line.

That is prose asserting a property the code lacks, and it is the more dangerous kind because it stops the next reader from checking. The annotation is retained (it is genuinely useful in-run context) and the emitter now runs alongside it, with a comment recording that the annotation is NOT the alert.

### Two earlier assertions narrowed, not deleted

The publication authority's job-set assertion now expects `alert` alongside `validate` and `publish`. The orchestrator's terminality assertion now excludes failure-only jobs from the dependent set, because the alert job is not a chain stage: it runs solely under `failure()`, produces nothing, and cannot extend a release past the seal. Both stay exact rather than becoming permissive, so a real third writer or a real post-seal stage still reds.
