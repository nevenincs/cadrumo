---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:1c40b4b8d2aeec087d1d818e6a2ee63b9d82fc6419ecc8b24d7007a42ea55ed4'
step_id: 'S06'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Prove the profile projection from real schema conditional-completeness filing-preflight selector and stored-fact inputs without presentation inference

## Scope

- `src/cadrumo/application/user_profile/tests/test_presentation.py`

## Changes

- `A` `src/cadrumo/application/user_profile/tests/test_presentation.py`
- `verify:` `pytest src/cadrumo/application/user_profile/tests/test_presentation.py -m integration` -> `pass` (9 passed)

## Notes

Named `test_presentation.py`, not `test_overview.py` as the Step row names:
that filename is already taken by `overview.py`'s own test file. Drives
the real production schema through `register_profile_with_credentials` and
real `UserProfileFact` writes (no synthetic schema, since
`build_profile_presentation` resolves the one committed
`load_user_profile_schema()`), proving: an unanswered trigger field yields
`NEEDS_APPLICABILITY` rather than `NOT_APPLICABLE` or a fabricated
missing-value claim; answering the trigger toward the gated value promotes
the conditional field to `APPLICABLE_REQUIRED_MISSING`/`PRESENT`; answering
it away from the gated value settles `NOT_APPLICABLE`; an unconditionally
required blank field blocks `ready`; the real `aeat_censo_read` provenance
token classifies as `AEAT_CENSUS_ACQUISITION`; and the model's own
cross-field validators (present-requires-source,
needs_applicability-requires-unassessed, blocks_ready-matches-classification)
reject a contradictory construction. Full suite run of
`application/user_profile/` shows 31 pre-existing failures elsewhere in the
package (custody/login-handover/atomic-create-roundtrip and others),
none touching `presentation.py`; the team lead independently traced a
concurrent relocation campaign (`96bb9e08a2`) leaving that package's
`__init__.py` inertness landed without its full consumer sweep as the
likely cause, not this Step.
