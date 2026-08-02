---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:e5997bdd0b768c7e69eb3020de5477b0701beb76449b272278a41c6b3e6b5b24'
step_id: 'S02'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Invert test_preflight_enforces_the_human_approval_gate_it_promises into a gate asserting that no job reads an environment protection rule, that no job conditions on required_reviewers, and that environment release survives on the publish job, so the removal is an asserted property a later honesty pass cannot silently restore, gate: uv run --no-sync pytest dev/release/tests/test_publish_release_workflow.py -q passes and a planted job re-adding a protection-rule read reds the new assertion

## Scope

- `dev/release/tests/test_publish_release_workflow.py`

## Description

- Replace `test_preflight_enforces_the_human_approval_gate_it_promises` with `test_no_job_gates_the_publication_on_a_human_protection_rule`, asserting the absence of any protection-rule read, the absence of any approval-conditioned job, the absence of the retired job name, and the survival of `environment: release` on the publish job.
- Factor the two matchers into module-level helpers so the same logic serves both the real gate and a planted-document control.
- Add `test_the_protection_rule_pin_reds_on_a_planted_reader` planting a protection-rule-reading job, an approval-conditioned job, and a clean job, so neither matcher can rot into one that matches nothing or everything.
- Update the three incidental references to the deleted job in the shape, dry-run, and OIDC-confinement tests.

## Outcome

The gate reports 94 passed. The removal is now an asserted property: an agent reading the three 2026-07-27 records and concluding the approval gate went missing cannot restore it without redding this test.

The positive control is stronger than the planted document the Step asked for. The matcher was run against the real pre-deletion workflow recovered from HEAD and returned exactly `{'operator-preflight'}` - so the pin is proven to catch the actual code that was removed, not merely a synthetic shape authored to match the matcher. That distinction matters here: a control written by the same author as the matcher can agree with it and still both be wrong about the real surface.

## Notes

Co-landed with S01 in one commit; the mutual dependency is recorded in the S01 record and carried to the S39 honesty review.

One judgement call on scope. The `_COMMAND_POSITION` anchoring comment at the top of the file explains itself by citing the operator-preflight refusal text that quoted a publish verb as prose. That text is now deleted, so the comment's stated reason no longer exists in the tree, but the anchoring itself remains correct and defensive and other comment prose still quotes verbs. The comment was left in place rather than rewritten, because rewriting it belongs to S03's prose sweep and splitting a prose change across two Steps is how a half-swept surface happens. Flagged to S03.
