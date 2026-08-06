---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:6a4b5f422729a1244afb653429b34f5015c06a28851e9d0757781cb0dc3fbe95'
step_id: 'S56'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Define the authoritative deletion-relevant bucket fingerprint for assessment and resume

## Scope

- `src/cadrumo/application/bucket_maintenance/_manifest_digest.py`

## Description

- Add `compute_bucket_deletion_fingerprint` returning a structured `BucketDeletionFingerprint` carrying the content digest, manifest digest, included-file count, and total byte count.
- Visit regular files recursively in relative-path order and fold the bucket identifier, structured manifest digest, each relative path, per-file content hash, and byte count into one deterministic digest.
- Exclude transient names ending in `.lock`, `.tmp`, or `-shm` through a named classification helper so a lock or journal artefact cannot perturb the fingerprint between assessment and deletion.
- Add `validated_bucket_deletion_paths` refusing a link-like bucket root before any manifest read, so a symlink or Windows junction cannot redirect assessment into storage outside the configured bucket directory.
- Refuse a missing bucket, a link or junction encountered below the bucket root, and a bucket containing no durable files.
- State explicitly in the contract that the function acquires no lock, making the caller responsible for holding the target stable across the read.

## Outcome

- One authoritative fingerprint now serves both assessment and resume, so the value recorded in the journal at snapshot time is directly comparable to the value recomputed under the deletion lock.
- Ordering is deterministic by relative POSIX path, so the digest is stable across platforms and directory-iteration order.
- Transient-file exclusion prevents a spurious fingerprint divergence that would otherwise pause a legitimate resume.
- Link refusal is enforced before the manifest is read, closing a redirection path that would let assessment or deletion escape the bucket directory.
- Landed in commit `11356b4792`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- The exclusion policy is documented as a naming classification and does not assert that every excluded file is inherently non-durable.
