---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:7d1d9405fe269e9211382b18cecbae9163fa134b91c86cbd9a32bba1997f013c'
step_id: 'S16'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Preserve the established recovery fingerprint across verification and recovery operations

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_record.py`

## Description

- Add a `recovery_fingerprint` computed property to the recovery envelope record, deriving a SHA-256 digest over the non-secret wrap material (ciphertext, nonce, tag), the HKDF info string, and the word count.
- Surface the fingerprint through the status, verify, and recover result records.

## Outcome

The established recovery fingerprint is preserved across verification and recovery. Verify reads the envelope without writing it, and recover rewraps the master key without touching the recovery envelope, so reloading yields the same fingerprint. The digest carries no plaintext mnemonic and no master key.

Evidence attributed at HEAD. Commit `b1d80821c9` (2026-07-17) adds 24 lines to `src/cadrumo/adapters/persistence/storage/master_key/_recovery_record.py`. At HEAD `RecoveryRecord` exposes `recovery_fingerprint` as a `@property`, joining `wrapped_dek_b64`, `nonce_b64`, `tag_b64`, `hkdf_info`, and the mnemonic word count and hashing them through the canonical `sha256_hex` helper rather than an inlined `hashlib` call. Every input is already public ciphertext or a constant, so the secret-free claim is verifiable by inspection of the digest inputs rather than taken on trust. Because it is a property and not a model field, the persisted envelope shape is unchanged. The fingerprint is surfaced on `RecoveryLifecycleStatus`, `RecoveryEnrollmentOutcome`, `RecoveryVerifyOutcome`, and `RecoveryRecoverOutcome` in `_recovery_facade.py`; `recovery_recover` captures the fingerprint into `established_fingerprint` before unwrapping and returns that captured value, and never writes the envelope path. Preservation is proven by `test_recovery_verify_reports_match_and_preserves_fingerprint` and `test_recovery_recover_rewraps_master_key_and_preserves_fingerprint` in `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py` (25 collected, 25 passed), and the secret-free and deterministic properties by `test_recovery_fingerprint_carries_no_secret_and_is_stable` in `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py` (26 collected, 26 passed).

## Notes

Documentation reconciliation only; the step was not re-executed. The originating record `S75` carries an identical heading and identical scope file, so the map to `S16` is exact.

The `date` frontmatter is deliberately the landing date `2026-07-17`, not the reconciliation date `2026-07-25`.

No substantiation gap for this step.
