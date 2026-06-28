---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S01'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Replace export-archive HKDF sealing-key derivation with Argon2id and persist the kdf params in the recovery-wrap member

## Scope

- `src/aeat/application/bucket_maintenance/_service.py`

## Description

- Replace the HKDF recovery-wrap sealing-key derivation with Argon2id
  (`derive_kek_with_params` at the OWASP baseline) over a fresh per-archive salt,
  on both the export and import paths.
- Rewrite the recovery-wrap member to record `{kdf: argon2id, salt_b64,
  memory_cost, time_cost, parallelism}`; `_recovery_wrap_kdf` reads and validates
  them (non-positive refused). Promote `derive_kek_with_params` + the Argon2
  constants to the master_key package surface.

## Outcome

An exported recovery-passphrase archive is no longer offline-brute-forceable: the
sealing key now costs a full Argon2id derivation per guess. Per no-legacy the
prior hkdf-sha256 format is deleted. 80 bucket_maintenance + master_key tests
green. Committed in `d8abf5673`. Unblocked once the peer tree-sweep cleared the
prior WIP on `_service.py`.

## Notes

A wrong-passphrase or tampered-low-cost member self-defeats (derives a different
KEK that cannot decrypt the AEAD payload) in addition to the explicit refusals.
