---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b14389e7f8af195b29e25a3e1200d71ace54d9ab078ba30bd4a25aeadd245a75'
step_id: 'S10'
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
     The S10 and 2026-08-07-history-onboarding-plan placeholders are machine-filled by
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
     The enroll app live filed pull-all in PROFILE_BOUND_WRITE_VERB_PATHS, verified by the existing write-policy guard test asserting the new path is recognised as profile-bound and ## Scope

- `src/cadrumo/application/storage_write_policy.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# enroll app live filed pull-all in PROFILE_BOUND_WRITE_VERB_PATHS, verified by the existing write-policy guard test asserting the new path is recognised as profile-bound

## Scope

- `src/cadrumo/application/storage_write_policy.py`

## Description

- Enroll `app live filed pull-all` in `PROFILE_BOUND_WRITE_VERB_PATHS`.

## Outcome

`pull-all` persists, so it is profile-bound. `discover` is deliberately NOT
enrolled: it reads the register's option lists and persists nothing, and enrolling
a read-only verb would put a write guard in front of a verb that cannot write.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/ src/cadrumo/application/overview/tests/ \
      src/cadrumo/entrypoints/cli/tests/test_app_live_filed_discover.py \
      src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py \
      src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py \
      src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py \
      src/cadrumo/agent/tests/test_rule_surface_conformance.py -q -n0 -m "unit or integration"
    1147 passed, 2 deselected in 155.20s (0:02:35)

## Notes

The enrolment and the verb it names were authored in the same working tree and
landed together, so the allowlist never referenced a verb that did not exist and
the verb was never reachable without its guard.
