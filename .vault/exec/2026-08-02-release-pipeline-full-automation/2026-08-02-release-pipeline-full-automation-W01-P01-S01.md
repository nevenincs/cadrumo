---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:3c8235dab8b266913935958a25df205d0277c996f436f4320469ec0fc6c72051'
step_id: 'S01'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Delete the operator-preflight job and the needs operator-preflight edge on the validate job from the publication authority, leaving environment release intact on the publish job because it is the Trusted Publishing trust anchor and the shared-runner product boundary, gate: uv run --no-sync pytest dev/release/tests/test_publish_release_workflow.py -q passes with the job absent from the parsed document and the publish job environment still asserted as release

## Scope

- `.github/workflows/publish-release.yml`

## Description

- Delete the `operator-preflight` job in full from the publication authority, including its lone step, its fail-closed refusal heredoc, and the dry-run warning branch that let the diagnostic proceed while the rule was absent.
- Delete the `needs: operator-preflight` edge from the `validate` job, leaving `validate` as the entry job of the workflow.
- Leave `environment: release` untouched on the `publish` job.

## Outcome

The publication authority now carries two jobs, `validate` and `publish`. Nothing in the workflow reads the environments API, and no job conditions on human-approval state. `environment: release` survives on the publish job, so Trusted Publishing still anchors on the workflow-run identity plus the environment name and the shared-runner product boundary is unchanged.

The gate `uv run --no-sync pytest dev/release/tests/test_publish_release_workflow.py -q` reports 94 passed.

## Notes

Co-landed with S02 in one commit, deliberately, and this is a plan defect worth recording rather than a shortcut. The two Steps are not independently green: the conformance suite reaches into the deleted job by name in four places, so deleting the job without inverting the test raises `KeyError`, and inverting the test before deleting the job fails on a job that still exists. Either ordering commits a knowingly-red gate, which the plan-closure discipline forbids. The honest unit is one commit carrying both, so both Step records name the same commit.

The plan's Parallelization prose already ordered S01 before S02 and stated the dependency; what it missed is that the dependency is mutual rather than one-way. Recorded for the campaign honesty review at S39.

No peer WIP was present on either file: `git status --short` over the workflow, `dev/release/`, and the runbook was clean before the first edit.
