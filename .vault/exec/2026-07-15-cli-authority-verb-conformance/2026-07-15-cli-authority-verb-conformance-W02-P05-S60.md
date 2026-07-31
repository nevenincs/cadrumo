---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:4911a3d037aabc1f5f0e209998507164a8771cee623b56178534e58c2d5301ff'
step_id: 'S60'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Persist reset journals atomically outside target directories with restrictive permissions and corruption refusal

## Scope

- `src/cadrumo/application/_config_reset_repository.py`

## Description

- Root the journal directory at a dedicated `reset-operations` directory directly under the local storage root, a sibling of the bucket directories rather than a child of any target, so the journal survives the deletion of every bucket it describes.
- Write each journal as an individual file named for its operation identifier, routing every write through the canonical hardened atomic text writer so a crash mid-write cannot leave a partial document in place.
- Apply restrictive permissions: mode `0o700` on the journal directory and `0o600` on each journal file.
- Serialise every create, replace, and incompleteness probe behind an exclusive file lock held on a dedicated lock target inside the journal directory.
- Add `create_exclusive` refusing a new operation while another journal is incomplete, and `refuse_if_incomplete` as the standalone preflight probe.
- Refuse corruption on load: a missing or unreadable file, malformed JSON, a schema-invalid payload, a future or unknown schema version, a filename-to-payload identifier mismatch, and a link-like journal path each raise rather than returning a partially trusted document.
- Validate the existing root before load and refuse a link-redirected root so the journal directory cannot be pointed into a bucket.
- Add `verify_deletion_ownership` resolving one target from the durable journal and confirming target presence, owned fingerprint, resolved retention, and a matching deleting marker.
- Validate the operation identifier before it is used to build any path.

## Outcome

- The journal is durable across the operation it describes: it lives outside every target directory, so an all-profile reset cannot delete its own resume evidence.
- Every write is atomic and lock-serialised, so a concurrent writer or a crash cannot produce a torn or interleaved document.
- Corruption, schema drift, filename mismatch, and link redirection are all load-time refusals rather than tolerated reads, so a damaged journal cannot silently authorize a deletion.
- The ownership verification helper is the single place the deletion path consults to prove a target erase belongs to a live operation.
- The repository deliberately exposes no journal-deletion API, so resume evidence cannot be discarded through this surface.
- Landed in commit `11356b4792`, with the directory-permission convention converged in `590c6cc28f` and the ownership validators decomposed into named helpers in `9851e08ae8`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- The repository documents honestly that it provides no MAC, signature, or other cryptographic authenticity proof; validation establishes structural integrity, not authenticity.
- The journal carries no passphrase, mnemonic, key, or decrypted payload, so its non-secret classification holds even though it is written outside the encrypted buckets.
