---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:fa3d7524d8a37868262419c2a580a7f27a39329d19b7f0169a25228a6d7cb1ab'
step_id: 'S76'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove create refusal, rotate preconditions, candidate verification, and old-envelope survival with real encrypted files

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py`

## Description

- Add real-encrypted-file tests provisioning a file provider under `tmp_path` and exercising the full lifecycle.
- Prove create refuses an existing enrollment and leaves the original bytes intact; prove rotate requires an existing enrollment.
- Prove candidate verification: a matching retype installs, and a mistyped or cancelled retype raises while leaving the prior envelope byte-identical (or writing nothing on first enrollment).
- Prove verify and recover report and preserve the fingerprint and that recover reopens the store under the new passphrase with the same master key.

## Outcome

Ten real-behavior tests cover the create-refusal, rotate-precondition, candidate-verification, and old-envelope-survival contracts against real Argon2id-backed file custody. `uv run --no-sync pytest src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py -q` reports 25 passed.

## Notes

`RecoveryVerificationError` renders through a translated message key, so its `str()` is empty; the failed-confirmation tests assert on the exception type and on the byte-identical envelope rather than on message text.
