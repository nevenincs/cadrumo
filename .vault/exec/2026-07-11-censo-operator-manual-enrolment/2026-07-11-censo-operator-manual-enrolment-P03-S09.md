---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S09'
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
     The S09 and 2026-07-11-censo-operator-manual-enrolment-plan placeholders are machine-filled by
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
     The Pin that operator-entered censal facts are never stamped AEAT-verified: nothing writes the aeat_censo_read or aeat_censo_derived source tags, so the calendar verified-key set stays empty and ## Scope

- `src/aeat/application/user_profile/tests/test_censo_sync.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Pin that operator-entered censal facts are never stamped AEAT-verified: nothing writes the aeat_censo_read or aeat_censo_derived source tags, so the calendar verified-key set stays empty

## Scope

- `src/aeat/application/user_profile/tests/test_censo_sync.py`

## Description

- Added `test_operator_manual_censo_facts_are_never_treated_as_aeat_verified` to the overview calendar verb tests: asserts `PROVENANCE_SOURCE_MANUAL_CLI` (the source `config profile edit` stamps) is not in the verified-source set `{aeat_censo_read, aeat_censo_derived}`, and drives the production `_live_censo_verified_profile_keys` over a profile carrying a manual-cli fact plus a censo-stamped fact, asserting only the censo-stamped path is returned.

## Outcome

The regression is green and non-tautological: it distinguishes the two sources through the real production filter, proving the empty result for operator-manual facts is the source-tag gate and not a vacuous return. This is the retirement analog of `app_filing not in _OFFICIAL_SOURCE_KINDS` from `local-filed-observations-are-non-official-evidence`.

## Notes

With the live scrape retired nothing stamps the verified censo tags, so a hand-entered profile always yields an empty verified-key set and the calendar keeps its unverified posture. Real-behavior test; no mocks.
