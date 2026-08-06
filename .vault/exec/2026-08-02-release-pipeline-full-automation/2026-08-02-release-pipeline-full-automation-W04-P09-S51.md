---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:fb4cd78c98a68df5cbd7e6c445b396f77e78a74e1adec27079d4d8b059163b48'
step_id: 'S51'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Extend the alert guards on the multi-job workflows and the promoter to cover cancellation as well as failure

## Scope

- `.github/workflows/release-orchestrator.yml`
- `.github/workflows/release-soak-promoter.yml`
- `.github/workflows/publish-release.yml`
- `dev/release/tests/test_release_alerting.py`

## Description

- Widen every release-path alert guard from `failure()` to `failure() || cancelled()`, including the docs publisher.
- Add the guard-scan assertion and its positive control.

## Outcome

16 passed in the alerting suite; 476 passed across the owned surface.

## Notes

`failure()` does not fire for a cancelled run, and a cancellation is not an exotic case here: a runner eviction on a shared four-runner fleet, or a concurrency interaction, cancels rather than fails. The release then ends with no result and no alert, which is exactly the silence this campaign exists to remove - and it is worse than a failure, because a cancelled run looks tidy in the run list.

The positive control matters more than usual for this assertion. A scan that read the wrong field would pass on a tree where every guard was still `failure()` alone, so the control constructs a failure-only guard and confirms the scan rejects it.

## Absorbed regression

Widening the guards broke `dev/deploy/tests/test_docs_publish_workflow.py::test_a_documentation_failure_cannot_unwind_the_release`, which selected the alert step by `step.get("if") == "failure()"` exactly. That assertion pinned the guard's SPELLING rather than its meaning, so a strictly safer guard broke it. Relaxed to containment with the reason recorded inline. The file carried no peer WIP, checked before editing.
