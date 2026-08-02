---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:79b166e2eeac991a1e6b94419e5dc3014aa3d13999f0a25917a62d98a7af2a3e'
step_id: 'S27'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Propagate dry_run through every orchestrator stage and onto the sealed candidate record so the rehearsal that previously proved Gates 1 and 2 now proves bump, campaign, acquisition, seal, and promotion without advancing a version or publishing a byte, gate: uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q passes asserting every stage reads the dry_run input and that the bump job pushes no ref and the promoter refuses to publish a dry_run candidate

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/release/soak_promoter.py`
- `dev/release/tests/test_release_orchestrator_workflow.py`
- `dev/release/tests/test_soak_promoter.py`

## Description

- Refuse a `dry_run` candidate in `promote_once` before the readiness re-check, with a reason naming the rehearsal.
- Assert the resolved `dry_run` reaches the bump and seal stages from the single `preflight` resolution.
- Assert the rehearsal and real bump are one code path differing by one flag.
- Add two orchestrator tests and one promoter test.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_orchestrator_workflow.py -q` reports 23 passed and `test_soak_promoter.py` 18 passed. Lint clean over my files.

The rehearsal now covers bump, campaign, acquisition, seal, and promotion. Before this pipeline it proved the two publication gates and nothing upstream, which would have left the four newly automated stages as the only ones never exercised without a real release.

## Notes

The promoter REFUSES a rehearsal candidate rather than filtering it out of selection, and the distinction is the whole point. A silently skipped rehearsal candidate is indistinguishable from no candidate having been sealed - which is exactly the failure the rehearsal exists to rule out. If the operator dry-runs the chain and the promoter says nothing, they learn nothing about whether the seal worked. Refusing visibly, with the version named and the soak reported as completed, means a rehearsal produces evidence that the whole chain including the wait actually ran.

The refusal sits before the readiness re-check, so a rehearsal does not spend a cohort download and a full gate run to reach a conclusion already determined by a flag on the record.

`dry_run` is resolved ONCE in `preflight` and read from that output by every later stage, rather than each job re-reading the raw dispatch input. Re-reading is how one stage ends up rehearsing while another commits for real - the two would agree in every test and diverge only under a condition nobody modelled.

The bump assertion checks that both `--dry-run` and `--push` appear in a single branch expression, pinning that the rehearsal and the real run are one code path with one flag differing. Two divergent paths would mean the rehearsal proves a path the real release never takes, which is a rehearsal of the wrong thing.
