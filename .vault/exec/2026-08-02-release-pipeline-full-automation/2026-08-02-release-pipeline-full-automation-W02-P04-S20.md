---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:d12f653e627da39d7b8d1ece6eaa671448b9a8345c07f2e8e844431487082a92'
step_id: 'S20'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Author the scheduled soak promoter workflow on a cron plus workflow_dispatch, running one short-lived job per tick on the self-hosted fleet under a product-scoped no-cancel concurrency group, invoking the selection logic and dispatching the publication authority with the run ids recorded on the candidate, so the soak boundary is crossed by a clock with no human re-entering the loop, gate: uv run --no-sync pytest dev/release/tests/test_soak_promoter_workflow.py -q passes pinning the schedule trigger, the runner labels, the concurrency group, the absence of any manual input that could shorten a window, and the dispatch target being publish-release.yml

## Scope

- `.github/workflows/release-soak-promoter.yml`
- `dev/release/soak_promoter.py`
- `dev/release/tests/test_soak_promoter_workflow.py`

## Description

- Author the promoter workflow on an hourly cron plus a dispatch carrying only a `report_only` boolean, on the self-hosted fleet, under a product-scoped no-cancel concurrency group, with a 20-minute timeout.
- Add the module CLI the workflow invokes, wiring the live forge dependencies: fetch sealed candidates, re-verify, dispatch, consume.
- Add `readiness_for_sealed_cohort`, re-downloading the cohort and its rows from the smoke evidence draft and pointing the gate at those rather than the working tree.
- Add `dispatch_publication`, passing the run ids the candidate recorded and omitting empty optional sources.
- Add seven conformance tests.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_soak_promoter_workflow.py -q` reports 7 passed, the four Phase-owned suites 48 passed, and the repository CI gates in `dev/ci/tests` 14 passed, so the new workflow satisfies the self-hosted-fleet and change-class gates it is subject to.

## Notes

The most consequential design point is what the dispatch form does NOT carry. A promoter with a `promote_now` or `soak_hours` input would be trivially convenient and would silently reintroduce the human act this whole design removes - on the one axis, time, that the soak exists to hold. The hotfix carve-out is authorised on the CANDIDATE instead, where an incident reference and a release-owner approval are recorded and refused at construction without both, so an emergency shortening is auditable from the artifact rather than typed into a form that keeps no record. The conformance test enforces this by pattern over input NAMES rather than by an allowlist, so a future input called `force_promote` or `skip_window` reds without anyone remembering to extend a list.

`readiness_for_sealed_cohort` points the gate at the re-downloaded cohort, never at the working tree. A working-tree run would answer a different question with the same green - "is this checkout sound" rather than "are the exact bytes that will ship still sound" - and the second is the only one the soak cares about.

The promoter deliberately holds no publication credential and does not run in the release environment: it dispatches the publication authority and nothing more. A promoter that could upload would be a second publication path bypassing Gate 2 entirely. That is asserted both by permissions and by scanning the run surface for publish verbs.

One typing decision. `promote_once`'s `consume` parameter is annotated as returning `object` rather than `None`, because the real consumer returns the retired tag it moved the candidate to; pinning `None` would force the callsite to discard a genuinely useful value to satisfy an annotation.

## Not verified here

Live execution is CI-only and BLOCKED on the operator items: nothing has run a real tick against the forge, so the cron cadence, the real dispatch, and the retag are proven structurally and by unit test rather than by observation. The end-to-end chain also cannot run until W03 seals a candidate, since there is nothing on the forge for the promoter to select yet.
