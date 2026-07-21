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

# Pin the calendar censo.enrolment_unverified posture with a regression: the warning is present and strict projection refuses for modelos 100/130/303/390 when censo is unverified

## Scope

- `src/aeat/application/overview/tests/`

## Description

- Added `test_calendar_keeps_unverified_posture_when_no_censo_is_verified` to the overview calendar unit tests: builds the calendar over a full-year range for the autónomo fixture with an EMPTY `live_censo_verified_profile_keys` (the post-retirement reality) and asserts no entry is VERIFIED, every present censo-dependent modelo (100/130/303/390) is UNVERIFIED, and the `censo.enrolment_unverified` warning lists each.

## Outcome

The regression is green. The CLI-level strict-projection refusal (`aeat app overview calendar` exits non-zero on the unverified posture) is already pinned by the existing `test_calendar_blocks_profile_derived_enrolment_without_live_censo`, so the honest default is covered at both the application and entrypoint layers.

## Notes

Real-behavior test against the real registry-backed calendar projection; no mocks. The `censo_enrolment_state` UNVERIFIED assertion is the concrete surface of the ADR's "refuses strict projection when censo is unverified" posture.
