---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:4853304db6402525d07463b8aa61ea65a9f347b7ae2b1310301bf79ccdc8f6c1'
step_id: 'S28'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Implement the resume input so a dispatch naming an existing packaging-smoke run re-enters the chain at the acquisition stage without re-bumping or re-running the campaign, letting a chain that failed after a successful campaign converge instead of burning a second version, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the bump and campaign jobs are skipped when resume is supplied and that the supplied run is identity-verified on the same terms Gate 2 verifies it

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/release/tests/test_release_orchestrator_workflow.py`

## Description

- Verify a resumed run before trusting it: successful conclusion, packaging-smoke workflow path, this repository, and main-ancestry via the compare API.
- Skip the bump entirely when a resume is supplied.
- Short-circuit the campaign job to the verified run's head commit rather than bypassing the job.
- Add three conformance tests.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q` reports 26 passed, `dev/ci/tests` 14 passed, lint clean. This closes Phase W03.P05.

## Notes

The resume input is the only place in the whole orchestration where an operator still types a run id, which makes it the only place a wrong one can enter - so it gets exactly the verification Gate 2 applies to a hand-supplied run: conclusion, workflow path, repository, and main-ancestry. Unverified, a resume could carry a foreign, failed, or never-landed campaign's cohort straight to a sealed candidate, and every later hash check would pass, because that cohort is internally consistent. It simply would not be this release's.

The main-ancestry check is the one most easily dropped as pedantic. It is not: a cohort built off a branch that never landed is reachable by run id forever, and without the ancestry test a resume could publish bytes from a commit that is not on main.

The resume path REUSES the campaign job rather than bypassing it. Bypassing would mean the seal reads its packaging run id from one place on the normal path and another on the resume path - two sources for one fact, which is how they drift. Instead the campaign job short-circuits internally and emits the same two outputs either way.

That reuse is what makes the `always()` guard from S23 load-bearing rather than incidental, and the test now pins both halves: `always()` so a deliberately skipped bump does not skip the campaign, and `needs.bump.result != 'failure'` so a genuinely failed bump still stops the chain. Keeping "skipped" distinct from "failed" is the whole content of that condition.
