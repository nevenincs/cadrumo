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

# Pin that operator-entered censal facts are never stamped AEAT-verified: nothing writes the aeat_censo_read or aeat_censo_derived source tags, so the calendar verified-key set stays empty

## Scope

- `src/aeat/application/user_profile/tests/test_censo_sync.py`

## Description

- Added `test_operator_manual_censo_facts_are_never_treated_as_aeat_verified` to the overview calendar verb tests: asserts `PROVENANCE_SOURCE_MANUAL_CLI` (the source `config profile edit` stamps) is not in the verified-source set `{aeat_censo_read, aeat_censo_derived}`, and drives the production `_live_censo_verified_profile_keys` over a profile carrying a manual-cli fact plus a censo-stamped fact, asserting only the censo-stamped path is returned.

## Outcome

The regression is green and non-tautological: it distinguishes the two sources through the real production filter, proving the empty result for operator-manual facts is the source-tag gate and not a vacuous return. This is the retirement analog of `app_filing not in _OFFICIAL_SOURCE_KINDS` from `local-filed-observations-are-non-official-evidence`.

## Notes

With the live scrape retired nothing stamps the verified censo tags, so a hand-entered profile always yields an empty verified-key set and the calendar keeps its unverified posture. Real-behavior test; no mocks.
