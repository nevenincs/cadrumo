---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:586475faee84da915ee35b0434690cf90f131f345b69d89f24d44a1484efaa13'
step_id: 'S110'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule on the bucket key enrolment ordering defect, since a bucket counts as registered purely because its capsule exists rather than by any stored enrolment, and registration permanently refuses minting by tested design, so the only window to mint the wrapped bucket key closes at capsule publication while the enrolment flag that opens it defaults false and is passed true by no production code anywhere, leaving no path that creates a bucket the storage layer will open

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_bucket_dek.py and src/cadrumo/application/user_profile/`

## Description

- Read the rejected sibling record in full before touching anything, per the
  standing instruction that a near-identical claim had already been measured
  wrong.
- Establish that every symbol the Step names is absent from the tree:
  `_master_key_bucket_dek.py`, `bucket_key_schedule`, `load_or_mint_bucket_dek`,
  `allow_bootstrap_mint` and the `BucketKeySchedule` enum.
- Drive the whole door end to end against an isolated real storage root:
  create, authenticate, then read.
- Inspect the live default store read-only for capsule-era buckets.
- Rule on the ordering claim and record the ruling in the sibling decision
  record scaffolded alongside this Step.

## Outcome

**The Step's premise does not survive corrected measurement.** Reported before
any conclusion, as the contract requires.

The Step asserts there is "no path that creates a bucket the storage layer will
open". The corrected probe ran the whole door with production symbols only, on
an isolated real storage root with a real custody envelope, a real Argon2id
supervised derivation and a real per-bucket encrypted store. Every step
succeeded:

- `register_profile_with_credentials` returned a bucket with
  `setup_state = incomplete`.
- `login_profile` authenticated, `session_persisted = True`,
  `already_authenticated = False`.
- `secure_object_repository_for_active_bucket().list_namespaces()` returned two
  real namespaces: the profile value namespace and the bucket event history
  namespace.
- `workflow_state_repository().load()` returned a `WorkflowState`.
- The profile record loaded, its `profile_id` equal to the created bucket id,
  `setup_state = incomplete`, zero facts.

The earlier claim came from stopping before authentication. Measured
separately, the same two reads refuse **before** login with
`StorageValidationError: errors.storage.runtime.not_ready`, and the profile
record read refuses with `ProfileNotFoundError: profile facts require an
authenticated session for this committed capsule`. Those refusals are the
lock registration deliberately installs, not evidence about key material. This
is the second time that confusion produced a defect claim.

**Which measurement shape this was, and whether the sequential-registration
handover refusal appeared in it.** Recorded explicitly, because a live ambient
defect on the login path could otherwise be mistaken for this Step's
enrolment claim, and the two have different causes and different remedies.

The measurement above creates exactly ONE profile per storage root and
authenticates it. The handover refusal
(`ActiveProfilePointerTransactionError: errors.integrity.integrity_storage_profile_custody_record`)
appeared in **none** of it: zero occurrences across every probe run, every
regression run and the 221-test session-substrate suite. The single place it
was observed during this work is an unrelated command-line test module already
red at HEAD, reported under Notes.

The sequential-registration case was then measured deliberately rather than
assumed away, and it does not reach this Step's conclusion by another route.
Two registrations followed by two authentications, in one process on one
storage root, succeed end to end: both buckets create, both authenticate,
and both read with one readable row and zero unreadable. An ordering matrix
localises the ambient defect precisely — it fires only when a registration is
performed while a session is already authenticated, after which the NEXT login
refuses whichever profile it targets, including the one already active.
Registering first and authenticating afterwards is clean, and repeated
authentication with no intervening registration is clean.

That defect is therefore a LOGIN failure, never a READ failure. In every case
where authentication succeeded, the records decrypted. It cannot produce a
bucket the storage layer will not open, which is what this Step alleges.

**The premise fails a second, independent way: its mechanism no longer
exists.** The retired keystore route was deleted ahead of this Step landing.
The module the Step names is gone, and so are the resolver, the mint helper and
the flag. The only `key_schedule` left in production is the custody envelope's
own `Literal["profile-password-dek-wrap/v1"]`. There is no resolver left to
mis-state a schedule and no mint window left to close.

A bucket created through the door today carries `custody/envelope.v1.json`,
`data/dek.sentinel.v1.json`, `profile.commit.v1.json` and `db/cadrumo.db`, and
carries no `manifest.toml` and no keystore entry — one custody, which is the
state the rejected record's option A described as the goal, reached by deletion
rather than by teaching a resolver to choose.

**Ruling.** A bucket is enrolled in the custody material it actually carries.
There is no ordering defect to repair, no unopenable bucket, and no change to
make. Minting a second wrapped copy of the DEK stays refused on exposure
grounds independent of the premise. Recorded in the decision record.

## Notes

Nothing was minted, migrated, repaired or deleted. No cryptographic parameter
was touched. All probe artefacts were written outside the repository.

Two stale references to symbols the keystore deletion removed survive outside
this Step's ownership and are reported rather than fixed:
`entrypoints/cli/tests/test_active_profile_env_override_name.py` imports
`BucketKeySchedule` and the retired manifest writer in a function-local block,
and `tests/test_persisted_version_literal_inventory.py` and
`application/bucket_maintenance/_manifest_digest.py` still name
`BucketManifest`. The first module is red at HEAD — two of its five tests fail,
though they fail earlier than the stale import, on the ambient handover
refusal.

The ambient handover defect is owned by its own row and was not touched here.
The localisation measured while ruling it out of this Step's evidence is
recorded because it narrows that row's search: the trigger is a registration
performed while a session is already authenticated, and the failure surfaces
on the NEXT authentication rather than on the registration itself, which is
why the command-line helper that authenticates after each registration
reproduces it while the raw application door does not. Passphrase reuse,
initial facts and the setup-completion step were each excluded by measurement.

The tree-wide import-hygiene and docstring-cross-link gates are broadly red at
HEAD from concurrent sweeps. The work added here contributes nothing to them:
zero occurrences of the new module across the 1498-line hygiene scan output.
