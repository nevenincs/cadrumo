---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:b409e4d5f0a7ad90ec203c1baaa24f42243308846d834ffa3b19484022230166'
step_id: 'S26'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Wire the candidate-seal stage as the orchestrator terminal job writing the release-candidate record and ending the run, so no orchestrator job holds a runner slot across the two-to-three day soak and the promoter alone resumes the chain, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the seal job is terminal, that no job sleeps or polls past the seal, and that the orchestrator never dispatches publish-release directly

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/release/seal_candidate.py`
- `dev/release/tests/test_release_orchestrator_workflow.py`

## Description

- Add `dev/release/seal_candidate.py`, downloading the sealed cohort, reading its identity from the cohort manifest, and minting the candidate through the tested module.
- Wire the terminal `seal` job.
- Add four conformance tests: terminality, no soak-waiting anywhere, the tested-module invocation, and module existence.
- Repair two of my own earlier assertions that this Step legitimately falsified.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q` reports 21 passed and `dev/ci/tests` 14 passed. Lint and `ty check` clean.

## Notes

Cohort identity is read from the cohort MANIFEST, never re-derived from the checkout. After a bump the working tree carries the same version, so re-deriving would usually agree - and would silently disagree in exactly the case that matters, when the campaign built something other than what this run believes it built. Reading the shipped bytes' own manifest makes the two impossible to confuse.

### Two of my own assertions were falsified, and both fixes are matcher fixes

`test_only_the_bump_job_may_write_repository_contents` (written in S22) failed because the seal job needs `contents: write` to create the candidate's draft. That assertion was correct when written and became wrong when the design gained a second legitimate writer. It is now an exact-set assertion over the writers, naming both and why each differs - `bump` lands a commit and tag, `seal` creates a draft in a reserved namespace that is not a publication. An exact set still reds on a third writer, so the guarantee narrowed in accuracy rather than in strength.

`test_the_orchestrator_never_publishes_and_never_dispatches_the_publication` failed on a false positive: my seal job's comment names `publish-release.yml` precisely to record that this workflow must never dispatch it, and the substring scan read the explanation as the violation. This is the same trap as the S03 header matcher, and the same resolution - fix the matcher, not the prose. Comments are now stripped before scanning, mirroring `_command_lines` in the sibling publication gate, which exists for exactly this reason. Had I reworded the comment instead, the workflow would have gone quiet about the single most important constraint it carries, in order to satisfy an instrument that was measuring the wrong thing.

The no-soak-waiting assertion deliberately scans the WHOLE workflow rather than the seal job alone, because the tempting shortcut - a sleep, a poll, an import of the promoter - could be added anywhere in the chain.
