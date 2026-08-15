---
tags:
  - '#adr'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:b4839b57ba6e8912095dbad75833e6f63f2a8a8ebda9f2e246a7be4991646204'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - '[[2026-08-13-profile-password-custody-research]]'
---
# `profile-password-custody` adr: `the bucket key schedule must report enrolled custody, not capsule existence` | (**status:** `proposed`)

## Problem Statement

A profile created through the surviving credential door cannot have any of its
records read. The bucket is discoverable, its capsule is recognised, and its
password custody material loads — and every record route refuses.

The decision is needed now because the ordering this depends on was never
decided. There is no ADR governing when a bucket's wrapped key is minted. The
nearest candidate, `2026-07-26-compatibility-enrollment-deadlock-adr`, governs
*format* enrollment for the compatibility checkpoint and states in its own
consequences that it "touched no key derivation, wrapping". So what exists is
not a decision to overturn but a gap left when the capsule cutover moved custody
and the schedule resolver kept answering the previous question.

The change itself is owner-gated under `no-legacy-compatibility`, which places
key-schedule and DEK-derivation changes outside autonomous authority. This
record exists so that ruling can be made without re-deriving the evidence.

## Considerations

- `bucket_key_schedule` returns `BUCKET_DEK_V1` on capsule recognition alone; it
  reads no stored enrolment (`master_key/_master_key_bucket_dek.py:36-56`).
- The sanctioned door mints the DEK and wraps it into the password custody
  envelope only; it never writes the bucket keystore
  (`application/user_profile/_registration.py`).
- The only production writer of `keystore/<id>/bucket.dek.json` is the mint
  branch inside `load_or_mint_bucket_dek`, reachable only when
  `allow_bootstrap_mint` is true. No production caller passes true; only tests do.
- Registration permanently closes the mint window by tested design
  (`test_registered_bucket_without_its_key_refuses_and_never_mints`).
- The affected bucket is not empty: it carries `db/cadrumo.db` written during
  capsule staging, alongside `custody/envelope.v1.json`,
  `data/dek.sentinel.v1.json` and `profile.commit.v1.json`.

## Considered options

**A — the resolver reports enrolled custody (chosen).** `bucket_key_schedule`
reads the custody a bucket is actually enrolled in rather than inferring a
master-key schedule from capsule existence, and the DEK route for
capsule-enrolled buckets resolves through the capsule's own custody material.
`BUCKET_DEK_V1` remains for buckets that genuinely carry a wrapped DEK file.

**B — the creation door mints the wrapped key before publishing (rejected).**
Ordering becomes the requirement and the verb merely the surface. Rejected on
security grounds rather than cost: see Rationale.

**C — relax the never-mint-after-registration guard (rejected outright).** Would
let a registered bucket acquire a second key silently, which is the state that
guard exists to make impossible. It also treats the symptom while leaving the
resolver's mis-statement in place.

## Constraints

- Owner-gated: `no-legacy-compatibility` places key-schedule and DEK-derivation
  changes outside autonomous authority. This record proposes; it does not enact.
- The guard pinned by `test_registered_bucket_without_its_key_refuses_and_never_mints`
  must remain correct and unweakened under whichever option is chosen. Option A
  satisfies this without modification, because a registered bucket never needs
  minting under it.
- No mature-library or frontier risk: the custody material this depends on is
  already produced, persisted and loadable today.

## Implementation

Two layers, and only the first carries the decision.

The schedule resolver stops equating registration with a master-key schedule. A
capsule proves the bucket is registered; it does not establish which key opens
it. The resolver reports the custody actually enrolled, so a capsule-created
bucket answers with its password custody rather than with `BUCKET_DEK_V1`.

The DEK route then follows the reported schedule: a capsule-enrolled bucket
resolves its key through the capsule's own custody material, which is present
and loads today; a bucket carrying a wrapped DEK file continues through
`BUCKET_DEK_V1` unchanged. Nothing new is written, and no second wrapped copy of
any key comes into existence.

The reproduction is pinned by
`master_key/tests/test_bucket_created_through_the_sanctioned_door_can_read_records.py`,
which fails today and is expected to fail until this is ruled on.

## Rationale

Option B loses on a security property rather than on effort, and that is the
knockout.

Minting `bucket.dek.json` before publication would create a second wrapped copy
of the same DEK under a different KEK, permanently, for every profile. A
keychain or master-key compromise would then yield the bucket DEK **without the
operator's passphrase** — defeating the exact property the capsule cutover was
undertaken to establish. It would also enrol every bucket in two schedules at
once, which is the one thing a key schedule exists to make unambiguous.

Option A rests on a fact the reproduction establishes: the DEK is not missing.
It is present, wrapped under the operator's passphrase, exactly where the cutover
put it. The resolver mis-states which custody the bucket is under. Correcting the
statement is smaller than manufacturing a second key, and it is the only option
that leaves the never-mint guard both correct and untouched.

## Consequences

**Nothing is stranded, and that empties the migration question.** Established by
reproduction rather than assumed: a bucket in this state is inert today. Its
capsule is recognised, it is listed as current, and its password custody material
loads — while both `workflow_state_repository().load()` and
`secure_object_repository_for_active_bucket()` refuse with
`StorageValidationError: errors.storage.runtime.not_ready`. No record can have
been written after creation, because no route to write one ever opened.

So option A is restorative rather than migratory. Every affected bucket holds
exactly its creation-time state, including a real `db/cadrumo.db` written during
staging, and the change makes that existing database readable through custody
material already on disk. There is no on-disk shape to convert and no window in
which a profile becomes less readable than it is now.

The honest difficulty is that this widens what the capsule route must support: a
custody path used at creation and login becomes the path every record access
depends on. That concentration is the price of not holding a second key, and it
should be weighed as such rather than assumed free.

Under option A the `BUCKET_DEK_V1` branch does not disappear — buckets that
genuinely carry a wrapped DEK keep using it — so this opens no purge and closes
no existing schedule.
