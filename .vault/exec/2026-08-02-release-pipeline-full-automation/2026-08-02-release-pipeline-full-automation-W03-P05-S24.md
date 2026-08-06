---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:48070cff6c4ed9363d0dc099d1d2d684eaee6e496a3801c2c3f28bfa645d78bf'
step_id: 'S24'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Wire the acquisition stage to dispatch exactly the lanes the claimed-channel derivation returns, passing its own smoke run id and head commit as each lane source_run_id and source_commit, resolving and waiting on each dispatched run, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting the lane set is derived rather than hardcoded and that today's python-only descriptor dispatches no acquisition lane

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/release/tests/test_release_orchestrator_workflow.py`
- `dev/packaging/publication_inputs.py` (same scope deviation as S22, reasoned there)

## Description

- Add an `--emit-lane-workflows` mode to the derivation module, printing the acquisition workflow paths the claimed channels require.
- Wire the `acquire` job to read that list and dispatch each lane through the run resolver, pinning `source_run_id` and `source_commit` to this campaign's own run and commit.
- Exit cleanly when the list is empty, which is today's correct behaviour.
- Add three conformance tests.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q` reports 14 passed and `test_publication_inputs.py` 30 passed.

Verified against the live descriptor rather than only in tests: `--emit-lane-workflows` prints nothing today, so the loop is legitimately empty, exactly as the Step predicted.

## Notes

The strongest test here asserts an ABSENCE: no lane workflow filename may appear literally in the acquisition stage. Asserting only that the derivation is invoked would pass just as happily with a hardcoded list sitting beside it, and that is the realistic regression - someone adds `packaging-scoop.yml` "temporarily" while the derivation returns nothing, and the two authorities silently fork.

The consequence of forking is worth stating because it is not obvious: the publication gate derives its REQUIRED evidence from the same descriptor. A hardcoded lane set that drifts means a channel flipped to `available` demands evidence at Gate 2 that no lane ever produced, so the release refuses at the very end of the chain - after the bump has burned a version - instead of dispatching one more run at the start.

The empty-lane assertion is bound to the shipped descriptor rather than a fixture, because the property that matters is that THIS repository's current claims produce no lane. That is what makes an empty loop correct rather than broken, and a fixture would assert the loop's shape while saying nothing about the tree.
