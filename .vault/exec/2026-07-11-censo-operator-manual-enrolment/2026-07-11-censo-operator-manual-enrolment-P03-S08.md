---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S08'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censo-operator-manual-enrolment with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-11-censo-operator-manual-enrolment-plan placeholders are machine-filled by
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
     The Pin the calendar censo.enrolment_unverified posture with a regression: the warning is present and strict projection refuses for modelos 100/130/303/390 when censo is unverified and ## Scope

- `src/aeat/application/overview/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Pin the calendar censo.enrolment_unverified posture with a regression: the warning is present and strict projection refuses for modelos 100/130/303/390 when censo is unverified

## Scope

- `src/aeat/application/overview/tests/`

## Description

- Added `test_calendar_keeps_unverified_posture_when_no_censo_is_verified` to the overview calendar unit tests: builds the calendar over a full-year range for the autónomo fixture with an EMPTY `live_censo_verified_profile_keys` (the post-retirement reality) and asserts no entry is VERIFIED, every present censo-dependent modelo (100/130/303/390) is UNVERIFIED, and the `censo.enrolment_unverified` warning lists each.

## Outcome

The regression is green. The CLI-level strict-projection refusal (`aeat app overview calendar` exits non-zero on the unverified posture) is already pinned by the existing `test_calendar_blocks_profile_derived_enrolment_without_live_censo`, so the honest default is covered at both the application and entrypoint layers.

## Notes

Real-behavior test against the real registry-backed calendar projection; no mocks. The `censo_enrolment_state` UNVERIFIED assertion is the concrete surface of the ADR's "refuses strict projection when censo is unverified" posture.
