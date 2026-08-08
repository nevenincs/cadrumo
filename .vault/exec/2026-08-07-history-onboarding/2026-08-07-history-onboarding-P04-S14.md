---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:aea860fd2a2e4977df79c255c1a25849b23b80f56d4c24ab37852f9936dbb3ba'
step_id: 'S14'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace history-onboarding with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-08-07-history-onboarding-plan placeholders are machine-filled by
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
     The add the cross-period next_action builder cases pointing at the new discover and pull-all verbs, verified by the existing next-action conformance coverage and ## Scope

- `src/cadrumo/application/modelo/_verification_cross_period.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the cross-period next_action builder cases pointing at the new discover and pull-all verbs, verified by the existing next-action conformance coverage

## Scope

- `src/cadrumo/application/modelo/_verification_cross_period.py`

## Description

- Add the `discover` and `pull-all` next-action mention to the cross-period fallback branch.

## Outcome

Confined to the FALLBACK branch on purpose. The targeted `pull-sources` verb stays
the action for a KNOWN upstream gap; a whole-history sweep is the right answer only
when the profile has no AEAT-sourced evidence at all, and offering it for a single
missing period would send the operator on a far longer run than the gap requires.
The reasoning is recorded beside the two constants so a later editor does not
"improve" it into every branch.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/ src/cadrumo/application/overview/tests/ \
      src/cadrumo/entrypoints/cli/tests/test_app_live_filed_discover.py \
      src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py \
      src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py \
      src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py \
      src/cadrumo/agent/tests/test_rule_surface_conformance.py -q -n0 -m "unit or integration"
    1147 passed, 2 deselected in 155.20s (0:02:35)

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
