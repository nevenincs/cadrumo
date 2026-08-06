---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:73530baf21b2f7daaa54c0fb95b8a2d5a2482d39db91d2b8ccd88b7b7eea894c'
step_id: 'S33'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Rewrite the RELEASING.md arming section to drop the approval-click prerequisite and the phantom CADRUMO_PUBLISH_ENABLED opt-in variable that no longer exists anywhere in the tree, replacing both with the OP-9 protection-rule removal and the credential prerequisites that genuinely remain, gate: rg -n CADRUMO_PUBLISH_ENABLED over the tree matches only vault records and history, and uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes

## Scope

- `RELEASING.md`
- `src/cadrumo/tests/test_release_config.py`

## Description

- Rewrite RELEASING.md's top summary paragraph, which claimed "the protected
  `release` environment's approval click is the human gate" -- a claim that
  contradicted the document's own `### Arm the publication workflow`
  section (already correct: "Do not add a required reviewer... there is no
  approval click"). Replaced with an accurate statement: neither the
  orchestrator nor the publication workflow reads a required-reviewer
  approval click in its own logic; the publish job still runs inside the
  `release` environment for its OIDC trust anchor, and that environment's
  `required_reviewers` rule, if not yet removed by the operator (OP-9), is a
  standing GitHub setting independent of anything the workflow enforces.
  Same correction applied inline in the new `### Publish` / Gate 3
  description (S32).
- Confirmed `CADRUMO_PUBLISH_ENABLED` was already fully absent from
  RELEASING.md and every other non-vault, non-history surface before this
  Step (W01 had already swept it); no further edit needed for that half of
  the gate. The one surviving tree mention, in
  `dev/release/tests/test_publish_release_workflow.py`'s
  `test_the_header_describes_the_gate_that_actually_runs` docstring, is a
  test explicitly asserting the variable's ABSENCE (historical commentary
  inside an anti-regression test, not a live instruction) -- out of this
  Step's declared Scope (`RELEASING.md,
  src/cadrumo/tests/test_release_config.py`) and left untouched.
- The `### Arm the publication workflow` section's numbered steps and the
  `### Operator actions` section (OP-9/OP-12/OP-3, already correct from the
  `#618` closeout Step) needed no further change: they already state the
  genuine remaining credential/settings prerequisites accurately.

## Outcome

Gate green: `rg -n CADRUMO_PUBLISH_ENABLED` over the tree matches only
`.vault/` records, `CHANGELOG.md`, and the one anti-regression test
docstring noted above (asserting absence, not describing presence).
`uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q` passes
9/9.

## Notes

None.
