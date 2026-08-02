---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:b2d8b13bed71d9971b088c64aa30f5196759c2a57b2f4cccb461db29a145d3ff'
step_id: 'S33'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace release-pipeline-full-automation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S33 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Rewrite the RELEASING.md arming section to drop the approval-click prerequisite and the phantom CADRUMO_PUBLISH_ENABLED opt-in variable that no longer exists anywhere in the tree, replacing both with the OP-9 protection-rule removal and the credential prerequisites that genuinely remain, gate: rg -n CADRUMO_PUBLISH_ENABLED over the tree matches only vault records and history, and uv run --no-sync pytest src/cadrumo/tests/test_release_config.py -q passes and ## Scope

- `RELEASING.md`
- `src/cadrumo/tests/test_release_config.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
