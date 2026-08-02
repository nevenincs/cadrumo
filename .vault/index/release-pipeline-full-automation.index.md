---
generated: true
tags:
  - '#index'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:61eb6b6dd28cb2729652a36d2681aa5789a35a6649b340df76767032e4066060'
related:
  - '[[2026-08-02-release-pipeline-full-automation-W01-P01-S01]]'
  - '[[2026-08-02-release-pipeline-full-automation-W01-P01-S02]]'
  - '[[2026-08-02-release-pipeline-full-automation-W01-P01-S03]]'
  - '[[2026-08-02-release-pipeline-full-automation-adr]]'
  - '[[2026-08-02-release-pipeline-full-automation-plan]]'
---

# `release-pipeline-full-automation` feature index

Auto-generated index of all documents tagged with `#release-pipeline-full-automation`.

## Documents

### adr

- `2026-08-02-release-pipeline-full-automation-adr` - `release-pipeline-full-automation` adr: `the release pipeline runs itself: the human approval gate is deleted, one dispatch drives bump through publish, and the mechanical guards are the whole safety net` | (**status:** `accepted`)

### exec

- `2026-08-02-release-pipeline-full-automation-W01-P01-S01` - Delete the operator-preflight job and the needs operator-preflight edge on the validate job from the publication authority, leaving environment release intact on the publish job because it is the Trusted Publishing trust anchor and the shared-runner product boundary, gate: uv run --no-sync pytest dev/release/tests/test_publish_release_workflow.py -q passes with the job absent from the parsed document and the publish job environment still asserted as release
- `2026-08-02-release-pipeline-full-automation-W01-P01-S02` - Invert test_preflight_enforces_the_human_approval_gate_it_promises into a gate asserting that no job reads an environment protection rule, that no job conditions on required_reviewers, and that environment release survives on the publish job, so the removal is an asserted property a later honesty pass cannot silently restore, gate: uv run --no-sync pytest dev/release/tests/test_publish_release_workflow.py -q passes and a planted job re-adding a protection-rule read reds the new assertion
- `2026-08-02-release-pipeline-full-automation-W01-P01-S03` - Rewrite the publication authority header comments that still promise an operator opt-in variable and an approval click, replacing them with the guard set that actually gates the run, and pin the corrected prose so the described gate and the enforced gate cannot drift apart again, gate: uv run --no-sync pytest dev/release/tests/test_publish_release_workflow.py -q passes with an assertion that the header names no approval click and no opt-in variable

### plan

- `2026-08-02-release-pipeline-full-automation-plan` - `release-pipeline-full-automation` plan
