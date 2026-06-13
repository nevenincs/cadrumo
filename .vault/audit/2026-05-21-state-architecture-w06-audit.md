---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-state-architecture-plan]]"
  - "[[2026-05-21-state-architecture-testimonial-regression-audit]]"
  - "[[2026-05-21-profile-state-aggregate-adr]]"
---

# `cli-workflow-redesign` audit: state-architecture W06 close

Closing note for Wave 6 (tombstone lifecycle correctness), the
testimonial-driven wave that closes the campaign.

## What landed

| Commit | Content |
|---|---|
| `b99081a76` | exclude tombstoned profiles from the live surface; `BucketManifest.status` marker; locale fix |
| `88a046367` | revision: cross-store drift integrity check + torn-write hardening |

The leak fix excludes tombstoned profiles from `list`, refuses
`switch` to them, makes `show` reflect the tombstoned status, and
restricts name / tax-id uniqueness to live profiles - so a deleted
profile's name is reusable, per the identity ADR. A plaintext
`status` marker on `BucketManifest` lets the manifest scan filter
without decryption.

## Review trail

Review found the leak genuinely closed on the happy path with good
roundtrip tests, but flagged that the status denormalization (status
now in both the encrypted record and the plaintext manifest)
introduced a drift risk: nothing detected a manifest status that
disagreed with the record, and `delete` had a torn-write window.
Revision `88a046367` closed both:

- `verify_profile_integrity` now rejects a manifest status that
  disagrees with the record status; `ProfileRepository.load` passes
  both. A hand-desynced manifest makes `load()` raise
  `ProfileIntegrityError` - confirmed live.
- `delete` writes the manifest tombstone mirror BEFORE the record
  tombstone, so a crashed delete fails closed (the profile drops off
  the live surface, the record stays loadable for repair) and the
  drift is detected on next load.
- A cross-store anti-tautology test, an enum value-sync test, and a
  docstring fix landed with it. The unused `noqa` was removed and the
  genuine `S112` it masked was fixed properly (debug-logged, no skip).

## Verification

- `application/user_profile` + `adapters/.../bucket`: 137 passed;
  the W06 revision tests (`test_profile_repository.py`,
  `test_aggregate.py`): 23 passed.
- Full `entrypoints/cli` tree: 484 passed, 3 failed - the same three
  foreign-WIP-blocked failures carried across the campaign.
- `ruff check` clean on every file touched.

## Campaign status

All six waves W01-W06 of the state-architecture plan are complete.
The profile management backend now has a stable UUID identity, a
single owning repository with a cross-store unit of work, a canonical
read-projection, one state root, and a correct tombstone lifecycle -
each verified by review and, end to end, by the testimonial
regression. Open items are external: the three foreign-WIP-blocked
CLI tests close when the owning campaigns commit; the `WorkflowEngine`
obligation-gate rewire and the `profile create` wizard-UX nit are
tracked follow-ups recorded in the plan and the W04 audit.
