---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:473684e11303336df2727ecb13940ec5503d047bab0c0f1056087ce589441d4a'
step_id: 'S31'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Add the alert-reachability gate asserting every workflow on the declared release path carries a failure alert, computing the release-path set from the workflows the orchestrator and promoter dispatch rather than a hand-maintained list, so a future release workflow added without an alert reds a test instead of failing silently in production, gate: uv run --no-sync pytest dev/release/tests/test_release_alerting.py -q -k reachability passes and an injectable-root self-test plants a release-path workflow with no alert step and asserts the gate reds

## Scope

- `dev/release/tests/test_release_alerting.py`

## Description

- Add `_needs_own_alert`, deriving the must-alert set from what the roots actually dispatch, following dispatches through the modules the roots invoke, and adding any workflow triggered by a release event.
- Add the coverage assertion, the planted-workflow control against an injectable root, and an explicit assertion of the deliberate exclusion.

## Outcome

The derivation independently computes exactly `{release-orchestrator, release-soak-promoter, publish-release, docs-publish}` - the four the plan names - without those names being written into the derivation. 12 passed in the alerting suite.

## Notes

### Following the dispatch through Python, not just YAML

A first version scanned only workflow text and silently missed `publish-release.yml`, the single most important workflow on the path, because the promoter dispatches it from inside `dev.release.soak_promoter` rather than from YAML. The gate would have reported full coverage while the publication authority had no alert at all - a reachability gate that is itself unreachable to the thing that matters most. The derivation now follows `dev.*` module references out of each root's run surface.

### Naming a workflow is not dispatching it

The next version over-reached the other way, demanding alerts on all three acquisition lanes. The host-extension precondition invokes `publication_inputs`, whose lane MAPPING names those workflows - but that step dispatches nothing. Module-derived names are now counted only when the module actually dispatches (`"workflow",` argv or `dispatch_and_resolve`).

### The narrowing is the real content, so it is pinned

A workflow whose dispatcher WAITS is already covered: a failed acquisition lane fails the acquire stage, which fails the orchestrator, which alerts. Giving the lane its own alert would deliver two alerts for one event - the same train-the-operator-to-filter failure that ruled out sending both an issue and a webhook. So the must-alert set is the roots, plus anything reached WITHOUT waiting, plus anything event-triggered off a release (the docs publisher has no dispatcher at all).

`test_a_waited_on_acquisition_lane_is_deliberately_excluded` asserts both halves: that the excluded lanes exist, and that the computed set is exactly the four. Without it, a derivation that quietly stopped discovering anything would satisfy the coverage assertion perfectly - the classic vacuous-green shape.

### Detector blindness

`_has_failure_alert` originally read only step-level `if`, so it reported both workflows carrying a correct job-level alert as unalerted. Both shapes are legitimate in their place, and a detector seeing one shape would either force the wrong shape or report a false gap; it now accepts either.
