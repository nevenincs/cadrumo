---
tags:
  - '#adr'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:0b1d23db7ea8a1db1ac8b672bb02a8ad4bbe4d81d67a3ab6c79fad0b0140efc7'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - '[[2026-08-13-profile-password-custody-research]]'
---
# `profile-password-custody` adr: `the bucket key schedule must report enrolled custody, not capsule existence` | (**status:** `rejected`)

## Problem Statement

**Rejected: the problem this record proposes to solve does not exist. The
original problem statement was wrong, and the error was in how it was
measured.**

It claimed that a profile created through the surviving credential door cannot
have any of its records read. That claim came from a probe which created a
profile and then immediately attempted a record read -- **without logging in.**
Registration deliberately closes the record session in a `finally` and returns
`setup_state = INCOMPLETE` (`application/user_profile/_registration.py`), so a
freshly created profile is LOCKED, not broken. Authentication is the design, not
a missing step. The probe observed the lock and reported it as a defect.

The corrected measurement uses production symbols only and runs the whole door:
create through `register_profile_with_credentials`, authenticate through
`login_profile`, then read. It succeeds --
`secure_object_repository_for_active_bucket()` returns a live repository,
`list_namespaces()` returns the real namespaces, and
`workflow_state_repository().load()` returns a `WorkflowState`. Instrumenting
`load_or_mint_bucket_dek` to record every call showed it entered **zero** times
across that path, and no `bucket.dek.json` was ever written: the keystore holds
only the acceleration receipt. The schedule resolver's answer was never
consulted on the working path, so there was nothing here for a decision to
repair.

That measurement outlived the record. It is what established the retired
keystore route as dead in production, and it is the evidence the deletion of
that route rests on.

The gap this record opens with was real: no ADR governed when a bucket's wrapped
key is minted, and the nearest candidate,
`2026-07-26-compatibility-enrollment-deadlock-adr`, genuinely governs *format*
enrollment rather than key derivation, stating in its own consequences that it
"touched no key derivation, wrapping". That gap closed by deletion rather than
by decision -- with the master-key keystore route gone, a bucket has one custody
and there is no schedule left to resolve.

**What survives rejection, and why this record is kept rather than deleted.**
The Rationale below refuses to mint a second wrapped copy of the same DEK under
a different key-encryption key, because a keychain compromise would then open a
bucket without the operator's passphrase. That argument never depended on the
false premise and remains the reason the never-mint guard must stay unweakened.
The ownership and exposure reasoning is the durable part; only the defect that
prompted it was imaginary.

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

**A — the resolver reports enrolled custody (not adopted; see Problem Statement).** `bucket_key_schedule`
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

**Not implemented.** This section is retained as authored, describing what the
change would have been, so a later reader can see what was weighed rather than
only that it was dropped. Nothing below was built.

Two layers, and only the first would have carried the decision.

The schedule resolver stops equating registration with a master-key schedule. A
capsule proves the bucket is registered; it does not establish which key opens
it. The resolver reports the custody actually enrolled, so a capsule-created
bucket answers with its password custody rather than with `BUCKET_DEK_V1`.

The DEK route then follows the reported schedule: a capsule-enrolled bucket
resolves its key through the capsule's own custody material, which is present
and loads today; a bucket carrying a wrapped DEK file continues through
`BUCKET_DEK_V1` unchanged. Nothing new is written, and no second wrapped copy of
any key comes into existence.

The test that pinned the supposed reproduction is gone. It asserted a record
read without an intervening login, which is not the contract, so it encoded the
measurement error rather than a defect. Deleting it was part of rejecting this
record; nothing replaced it here, because the property worth pinning belongs to
the keystore deletion instead -- that the working path needs no keystore route.

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

**The strand question has two populations, and the first version of this record
measured only one of them.** The correction matters more than the original
claim, because the unmeasured population is the operator's own data.

*Capsule-era buckets: nothing is stranded.* Established by reproduction rather
than assumed — a bucket created through the sanctioned door is inert today. Its
capsule is recognised, it is listed as current, and its password custody material
loads, while both `workflow_state_repository().load()` and
`secure_object_repository_for_active_bucket()` refuse with
`StorageValidationError: errors.storage.runtime.not_ready`. No record can have
been written after creation, because no route to write one ever opened. For this
population option A is restorative rather than migratory: the bucket holds
exactly its creation-time state, including a real `db/cadrumo.db` written during
staging, and the change makes that database readable through custody material
already on disk.

*Pre-capsule buckets: roughly six megabytes of operator data.* The live default
store at `AppData/Local/cadrumo/storage` holds four buckets that predate the
cutover entirely, measured 2026-08-15:

| bucket | label | manifest status | `db/cadrumo.db` |
|---|---|---|---|
| `3806b406-2d0c-47fb-a576-13644e08e737` | `<operator-username>` | `setup_incomplete` | 5,316,608 B |
| `d06d093f-f1cc-4f79-bb0d-219541836a99` | `operator` | `active` | 106,496 B |
| `f5556acb-6a12-4266-be5e-e3cfdc73c325` | `<operator-username>` | `tombstoned` | 516,096 B |
| `faa52bed-5708-4bf2-b974-ad9c658f5871` | `sync-test` | `tombstoned` | 311,296 B |

6,250,496 bytes of encrypted data in total, and the `active-profile` pointer
targets the first. Sizes are the database files alone; a per-bucket 32,768-byte
`-shm` companion accounts for a reader arriving at slightly larger figures.

Each carries `manifest.toml` and `keystore/<id>/bucket.dek.json` — both retired
surfaces — and the store contains **no capsule material of any kind**: no
`profile.commit.v1.json`, no `envelope.v1.json`, no `dek.sentinel.v1.json`, and
no `custody/` directory anywhere beneath it. These buckets depend on both
surfaces a no-legacy deletion would remove, and have nothing to fall back to.

**So the deletion is ordered, not merely authorised.** The retired route cannot
be removed while this store still depends on it, and of the two conceivable
orderings only one is available.

Migrating the buckets into custody first is closed on two independent counts.
The campaign's own closing step forbids it in terms — `W05.P08.S25` requires
that retired custody is never read, adopted or migrated — and it is in any case
unreachable without new code, because the current tree cannot read these
manifests at all. `read_manifest` raises `ValidationError` on all four: the
on-disk documents carry `recovery_enrolled` and `status`, which the strict
`extra="forbid"` `BucketManifest` does not declare, and they report
`schema_version = 2` against a current version and durability floor of 3.
Writing the reader that would make migration possible is exactly the
read-tolerance of pre-current shapes that `no-legacy-compatibility` forbids.

Disposal is therefore the sanctioned ordering. `W05.P08.S25` performs an
explicitly authorised local-only destructive reset of this store through the
canonical application-owned deletion authority, capturing journal and receipt
evidence and re-enrolling only current-format profiles, gated behind
`W05.P08.S24`, the final security and architecture proof of the hard cutover.
The legacy route may be deleted after that step has run, and not before.

**What "at stake" means here is recoverability, not working access.** These four
buckets are unreadable by the current tree today for three independent reasons,
none of which is the branch under deletion: no capsule, so `bucket_key_schedule`
resolves `None` and the `BUCKET_DEK_V1` arm is never reached; the manifest
schema floor; and the retired manifest fields above. Their only remaining door
is the bootstrap arm, which no production caller opens. The deletion would
therefore take away not access but the ability to recover — today the ciphertext
and its wrapped key are both on disk and the unwrapping helpers still ship
behind a test-only flag, so recovery is a small amount of code against existing
symbols, whereas afterwards it means reconstructing removed code from history.
That is a narrowing rather than an immediate loss, and it remains the operator's
call, which is why the sanctioned reset captures evidence rather than assuming
the data is disposable.

The honest difficulty in option A is that it widens what the capsule route must
support: a custody path used at creation and login becomes the path every record
access depends on. That concentration is the price of not holding a second key,
and it should be weighed as such rather than assumed free.

**Option A's retained-branch clause no longer stands.** The operator has since
ruled that no legacy survives anywhere in the codebase, which deletes the
`BUCKET_DEK_V1` branch rather than keeping it for wrapped-DEK buckets. This
record does not enact that ruling: the measurement above blocks it on ordering,
the change remains owner-gated, and this record stays `proposed`.
