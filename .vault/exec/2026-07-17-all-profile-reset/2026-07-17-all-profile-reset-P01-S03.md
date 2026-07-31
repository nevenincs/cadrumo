---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:be454415b448522bf1a19bf20c85e52250975c27ae44b32c71161c4c573f5b54'
step_id: 'S03'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Define the authoritative deletion-relevant bucket fingerprint for assessment and resume

## Scope

- `src/cadrumo/application/bucket_maintenance/_manifest_digest.py`

## Description

- Add `compute_bucket_deletion_fingerprint`: fold the bucket identifier, the structured manifest digest, and each durable file's relative path, content hash, and byte count into a single content-addressed digest, returning a structured `BucketDeletionFingerprint` (digest, manifest digest, file count, total bytes).
- Visit regular files recursively in relative-path order for a stable, order-independent digest; exclude transient files whose names end in `.lock`, `.tmp`, or `-shm` so lock and journal churn does not perturb the fingerprint.
- Add `validated_bucket_deletion_paths`: refuse a missing bucket, a symlinked/junctioned bucket root, and links or junctions below that root, so a redirected root cannot make external storage a target; refuse a bucket with no included files.
- Delegate byte-to-digest mechanics to `core.hashing` (`sha256_hex`, `hash_file`, `content_hash_hex`), keeping the caller's byte projection and domain separation local.

## Outcome

The fingerprint is the authoritative deletion-relevant identity used both for assessment and for resume: a change to the authoritative filing catalogue changes the digest, so a resume that rechecks it detects post-assessment drift and pauses. Proven by the P01.S04 tests (fingerprint stable across repeated assessment; digest changes when a real filing is added) and the P01.S05 link-redirection refusal (external sentinel and manifest survive byte-identical). Ruff clean.

## Notes

Landed in commit `11356b4792`; re-verified at HEAD. The fingerprint acquires no lock or transactional snapshot, so the caller (the service under its mutation target lock) is responsible for keeping the target stable across the read — documented in the function docstring.
