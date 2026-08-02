---
generated: true
tags:
  - '#index'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:b7053344235195d908b679aa6033fabb4cc996d6bdbb9c3e8fc2f5096070ab1c'
related:
  - '[[2026-08-02-release-pipeline-full-automation-W01-P01-S01]]'
  - '[[2026-08-02-release-pipeline-full-automation-W01-P01-S02]]'
  - '[[2026-08-02-release-pipeline-full-automation-W01-P01-S03]]'
  - '[[2026-08-02-release-pipeline-full-automation-W01-P01-S04]]'
  - '[[2026-08-02-release-pipeline-full-automation-W02-P04-S14]]'
  - '[[2026-08-02-release-pipeline-full-automation-W02-P04-S15]]'
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
- `2026-08-02-release-pipeline-full-automation-W01-P01-S04` - Record OP-9 as a named operator settings action removing the required_reviewers protection rule from BOTH the release and docs environments while keeping each environment and its branch_policy, and add a read-only forge inventory probe that reports each environment protection-rule set without mutating anything so the operator half is verifiable rather than assumed, gate: uv run --no-sync pytest dev/release/tests -q -k environment_inventory passes over fixture payloads covering a rule-present, a rule-absent, and an unreadable-environment response
- `2026-08-02-release-pipeline-full-automation-W02-P04-S14` - Declare the release-candidate record as a strict typed model carrying the cohort id, the version, the source commit, the smoke run id, every acquisition run id, the claimed channel set, the dry_run flag, the soak opened_at, and the computed soak deadline, with the window read from the release checklist soak hours rather than a new literal so one authority still owns the duration, gate: uv run --no-sync pytest dev/release/tests/test_release_candidate.py -q passes with a strict save-load-equality roundtrip populating every defaultable field non-default plus an anti-tautology proof deleting the deadline from the serialized payload and asserting the load refuses
- `2026-08-02-release-pipeline-full-automation-W02-P04-S15` - Publish the sealed candidate record through the existing evidence-release draft transport under a release-candidate tag keyed on the smoke run id, so the durable state lives outside every running job and outside the working tree exactly as the evidence rows already do, gate: uv run --no-sync pytest dev/release/tests/test_release_candidate.py -q passes over the writer and reader against injected release payloads, with live draft creation flagged non-local and CI-only

### plan

- `2026-08-02-release-pipeline-full-automation-plan` - `release-pipeline-full-automation` plan
