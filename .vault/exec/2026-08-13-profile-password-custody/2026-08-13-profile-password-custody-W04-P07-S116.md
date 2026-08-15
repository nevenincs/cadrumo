---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:0d45d5f6dee494001dc7a3114b33863be62205c78b60226bd44d2c3fe36b2134'
step_id: 'S116'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh delete the bucket manifest digest and deletion fingerprint helpers, exported from the maintenance package with zero production callers, being dead capacity rather than a dependency

## Scope

- `src/cadrumo/application/bucket_maintenance/_manifest_digest.py`

## Description

- Read `S147` and `S121`'s execution records before touching anything, per
  this row's own instruction, since S147 retired the manifest digest FIELD
  from the deletion contract and S121 ruled the fingerprint TYPE stays because
  it is a supersession-in-progress, not dead code.
- Read the current `S154` outcome (the live context this row's dispatch flagged):
  the deletion preflight now folds the committed-capsule inventory into
  `BucketDeletionFingerprint`, so the contract TYPE is a live, populated
  producer again.
- Confirmed by reading `_manifest_digest.py` that the module already carried
  only `validated_bucket_deletion_paths` and a private `_is_transient_bucket_file`
  helper — the two named-dead symbols (`compute_manifest_digest`,
  `compute_bucket_deletion_fingerprint`) and their zero-production-caller status
  were established.
- Ran `git log` on the file and found the deletion had already landed on `main`
  at commit `d9d7ff6fdc` ("delete the two manifest digest helpers nothing
  calls (W04.P07.S116)"), an ancestor of HEAD, with a message independently
  confirming the same boundary this row asked for.
- Verified via exact-symbol search that no reference to either deleted symbol
  remains anywhere in the tree outside historical `.vault/` prose.
- Ran the bucket-maintenance test suite to confirm nothing broke.

## Outcome

**Symbols proved dead and already deleted (by a peer, on `main`, ancestor of
HEAD): `compute_manifest_digest` and `compute_bucket_deletion_fingerprint`,**
both formerly exported from `application.bucket_maintenance._manifest_digest`
and re-exported nowhere in the package `__all__`. Both had zero production
callers; their sole test module (`tests/test_manifest_digest.py`) covered only
them and was deleted with them. `compute_manifest_digest` computed a
SHA-256 over a serialised `BucketManifest`, whose subject the plaintext-manifest
retirement removed; `compute_bucket_deletion_fingerprint` was a second,
superseded producer for `BucketDeletionFingerprint` duplicating the live
custody-capsule preflight `S121` identified and `S154` finished wiring.

**Symbols proved dead but explicitly NOT touched, because `S154` made them
live again:** the `BucketDeletionFingerprint` contract type itself (in
`application._bucket_deletion_contracts`), and `validated_bucket_deletion_paths`
plus the private `_is_transient_bucket_file` in the same module. The
fingerprint type is now populated by `_service.py`'s
`_fold_capsule_inventory_into_fingerprint` (verified by reading the current
`_service.py`, which imports `BucketDeletionFingerprint` from
`.._bucket_deletion_contracts` and constructs it from the committed custody
inventory digest, file count and byte total) — a real, live producer, not the
unreachable branch `S121` ruled on before `S154` wired it. Deleting the type
now would break a live producer; nothing in this row's scope touches it.
`validated_bucket_deletion_paths` is live at three call sites inside
`_service.py`, confirmed by grep before any edit; the module was correctly
kept rather than deleted wholesale, per the peer's own commit message
("The module itself stays... this is a removal of two functions rather than
of a file").

**What was deleted:** `compute_manifest_digest`, `compute_bucket_deletion_
fingerprint`, their `__all__` entries in `_manifest_digest.py`, and their
dedicated test module — all removed outright with no re-export, wrapper, or
deprecation alias, satisfying the no-legacy-compatibility contract. This work
was already committed on `main` (`d9d7ff6fdc`) before this row's dispatch
reached the file; this Step's contribution was independent verification
against current HEAD, not a re-do.

**Verification.** `git merge-base --is-ancestor d9d7ff6fdc HEAD` confirms the
deletion commit is on the current branch. An exact search for
`compute_bucket_deletion_fingerprint|compute_manifest_digest` across the tree
returns matches only inside `.vault/` execution and audit prose (historical
record, not live code). `pytest src/cadrumo/application/bucket_maintenance -q
-m "unit or integration"` passes 13/13 with no skips, xfails, or errors.

## Notes

No incidents. This row's own deletion work had already landed via a peer
commit by the time this Step began; the value this Step adds is the
independent re-verification the row asked for (confirm zero production
callers, confirm the fingerprint-type boundary against the live `S154`
wiring, prove the suite green) rather than a duplicate deletion.
