---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
---

# `secure-storage-production-hardening` `W20.P40.S457` custody rollout audit

## S457-001 | PASS | First-class custody verbs are mounted

The config CLI now exposes `lock`, `unlock`, `rekey`, `recover`,
`show-recovery`, and `verify-recovery` as first-class root commands under
`aeat config`. Direct help smoke checks for each command completed successfully.

## S457-002 | PASS | Recovery uses the accepted typed facade

The application custody service mints and persists `RecoveryRecord` envelopes
through `mint_recovery_envelope` and `save_recovery_envelope`, loads them through
`load_recovery_envelope`, verifies mnemonics through
`verify_recovery_mnemonic`, and recovers the DEK through
`unwrap_recovery_envelope`. The legacy wrapped-master-key primitives remain
available for their existing low-level tests but no longer drive the new config
custody verbs.

## S457-003 | PASS | Bucket/profile lifecycle remains the lock and unlock path

`config unlock` selects the requested or active profile through the canonical
profile lifecycle span, while `config lock` uses the same active-profile logout
primitive as the existing profile command. This preserves the accepted
bucket-session lifecycle rather than adding a parallel lock path.

## S457-004 | PASS | Locale work used the required CLI path

The custody CLI strings were populated through the `aeat.locales` command path,
and `uv run --no-sync python -m aeat.locales audit` reports all shipped locale
catalogues as valid: `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

## S457-005 | PASS | Real behavior tests cover recovery and passphrase rotation

The integration suite creates a real file-backend profile, runs
`show-recovery`, validates the persisted recovery file with the production
`RecoveryRecord` model, verifies that the plaintext profile manifest is marked
`recovery_enrolled = true`, verifies the generated mnemonic, rejects a malformed
mnemonic, rekeys the file secret store, recovers it under a fresh passphrase, and
reopens the encrypted profile after each passphrase change.

## S457-006 | PASS | Blocking backend regression repaired

The S457 CLI gate exposed a backend `NameError` in
`src/aeat/adapters/persistence/storage/sql/secure_objects.py`: revision metadata
used `json.dumps` without importing `json`. Restoring the import was necessary
to keep profile creation and secure-object writes functional under the verified
backend path.

Disposition: close `W20.P40.S457`. Remaining W20 work stays open for passphrase
bootstrap/redaction hardening, stale guidance replacement, guard narrowing,
remaining localization, provenance path review, and central redaction enrollment
proof.
