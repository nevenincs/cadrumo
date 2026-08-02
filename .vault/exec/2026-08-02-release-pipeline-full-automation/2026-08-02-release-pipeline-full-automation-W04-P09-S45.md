---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:88868f75ad958155d5608085ba6dfcae951f13911b0edb612c6e8fae51858316'
step_id: 'S45'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Carry every acquisition run id from the acquisition stage onto the sealed candidate record

## Scope

- `.github/workflows/release-orchestrator.yml`
- `dev/packaging/publication_inputs.py`
- `dev/release/tests/test_release_orchestrator_workflow.py`

## Description

- Declare the three acquisition outputs on the `acquire` job and set the three environment variables the seal module reads.
- Add `lane_output_name` to the derivation module and emit `<workflow>\t<output name>` pairs from `--emit-lane-workflows`.
- Pass `--output-name` per lane and refuse a lane whose output name is absent.
- Add three tests, one binding the workflow's env names to the module's own reads.

## Outcome

476 passed across `dev/release/tests`, the derivation suite, `dev/ci/tests`, and `dev/deploy/tests`.

## Notes

The audit is exact: the ids were computed and dropped at the job boundary. The seal module read three environment variables, the stage declared no outputs, and the seal step set none - three files agreeing to lose a value none of them referenced together. Vacuous today because the descriptor claims python alone, and armed the moment a channel is claimed, which is precisely when nobody is looking for it.

One of my own earlier assertions caught a mistake in my first fix, which is worth recording. I mapped lane to output name with a `case` block in the workflow, and S24's "no lane workflow filename appears literally in the acquisition stage" test red immediately. That assertion was right and my fix was wrong: naming the three lanes in YAML forks the lane authority, so a fourth lane would need edits in two places and would silently drop its id in whichever place was missed. The mapping moved into `publication_inputs` beside `LANE_WORKFLOW_BY_CHANNEL`, the derivation now emits the output name alongside the workflow, and the orchestrator names no lane at all.

`test_the_seal_reads_exactly_the_variables_the_module_consumes` asserts against the module SOURCE rather than restating the three names. The original defect was a silent mismatch between two files that never reference each other, so a test that listed the names a third time could have drifted in exactly the same way.
