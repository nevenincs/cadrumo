---
step_id: S20
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W02.P04.S20-S21-S23 — closed as out-of-rule misframing and duplicate coverage

## Scope

Adjudicate three Steps left open after the W02.P04 promotion sweep:

- `S20` — lift `profile_id` to `ProfileId` in `src/aeat/core/_bucket_pointer.py`.
- `S21` — lift `profile_id` to `ProfileId` in `src/aeat/core/config.py`.
- `S23` — add real-behavior roundtrip test populating a UserProfile
  with a non-default ProfileId through the real SecureObjectRepository.

## Outcome

Closed without code edits. Rationale below.

## Verification

Grep against the named modules. `src/aeat/core/_bucket_pointer.py`
declares `bucket_id` on its `BucketPointer` BaseModel; it carries no
`profile_id` field. The Step was misframed against the wrong field
identity. The bucket-identity surface is owned by W01 and was
relocated to `core/identity/_bucket.py` under ADR Rule 5.

`src/aeat/core/config.py` carries `aeat_active_profile` as an
environment-variable name on `Settings`; it has no pydantic-model
`profile_id: str` field for the alias to bind. `aeat_active_profile`
is a settings string, not a record identity, and falls outside
ADR Rule 9 clause 4 (`*_id` field on a pydantic model).

`src/aeat/application/user_profile/test_corporate_tax_facts_roundtrip.py`
and `test_irpf_special_regime_persistence_roundtrip.py` already
exercise the UserProfile / SecureObjectRepository roundtrip with
non-default `profile_id` values. The coverage S23 prescribed is
present; adding a duplicate test surface would violate the
no-duplicate-test discipline.

## Notes

S20 and S21 are misframings of the original ProfileId promotion
scope: the W02 executor correctly identified that those files do
not carry a pydantic-model `profile_id` field. S23 duplicates
existing coverage. All three are closed with this record as the
audit trail. No code edits land.
