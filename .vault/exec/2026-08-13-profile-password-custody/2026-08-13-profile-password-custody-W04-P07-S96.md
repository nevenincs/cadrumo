---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:af549a4b5a5c629264baa40f5208444861723e8c02ba37352278363e3325bfd1'
step_id: 'S96'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether test bucket identifiers must be profile identifiers, since production bucket identifiers ARE profile identifiers and a capsule cannot exist for any other shape, while the test surface has drifted to readable strings naming what each bucket is for, so every test using one is exercising a bucket configuration production cannot produce and no capsule-backed coverage can ever live there, and note the readable names carry real meaning so a sweep to identifiers loses information that would need somewhere else to live

## Scope

- `src/cadrumo/tests/secure_sql.py and src/cadrumo/application/user_profile/_capsule_record.py`

## Description

- Establish what shape production actually mints for a bucket identifier.
- Rule on whether the test surface may keep readable identifiers.
- Convert the drifted call sites and give the readable meaning a home.

## Outcome

**Ruled: a test bucket identifier MUST be a profile identifier, and the
readable name moves to the label the fixture already accepts.**

The ruling is not a preference. A production bucket identifier IS a profile
identifier and a capsule cannot exist for any other shape, so a test using a
readable string exercises a bucket configuration production cannot produce and
can never carry capsule-backed coverage. The shared fixture's own default was
already a canonical UUID, so the drift was in the call sites rather than in the
harness.

The Step worried that a sweep to identifiers would lose information the
readable names carry. It does not have to: the fixture already takes a separate
label, which is where "what this bucket is for" belongs. The drifted sites now
pass a canonical identifier and state their purpose in the label.

An attempt to keep both by DERIVING an identifier from the readable name was
made and abandoned, and the reason is worth recording: the persisted profile
record pins a version-4 UUID specifically, so a name-seeded version-5 value is
refused at construction. That failure is the same single-authority point the
row is about — inventing a second way to mint an identifier immediately
disagreed with the one the records enforce.

## Notes

A related disagreement surfaced and is NOT resolved by this row: the custody
path boundary deliberately accepts any UUID version, including nil and max,
while the persisted profile record accepts version 4 only. Two gates, two
answers to which strings name a valid profile. That is the substance of the
open row on identifier shapes and is left to it rather than absorbed here.
