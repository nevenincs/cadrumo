---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:d63fc2b2d383c561b14f4e0b9c71e2bda2bb903b9f94aeee9457e206cb165a7b'
step_id: 'S17'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove create refusal, rotate preconditions, candidate verification, and old-envelope survival with real encrypted files

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py`

## Description

- Add real-encrypted-file tests provisioning a file provider under `tmp_path` and exercising the full recovery lifecycle.
- Prove create refuses an existing enrollment and leaves the original bytes intact, and prove rotate requires an existing enrollment.
- Prove candidate verification: a matching retype installs, and a mistyped or cancelled retype raises while leaving the prior envelope byte-identical, or writing nothing on first enrollment.
- Prove verify and recover report and preserve the fingerprint, and that recover reopens the store under the new passphrase with the same master key.

## Outcome

Real-behavior tests cover the create-refusal, rotate-precondition, candidate-verification, and old-envelope-survival contracts against real Argon2id-backed file custody.

Evidence attributed at HEAD. Commit `b1d80821c9` (2026-07-17) adds 219 lines to `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py`. At HEAD that file carries the ten lifecycle tests the step names, confirmed individually rather than inferred from the count: `test_recovery_create_enrolls_and_status_reports_fingerprint`, `test_recovery_create_refuses_existing_enrollment`, `test_recovery_rotate_requires_existing_enrollment`, `test_recovery_rotate_replaces_envelope_after_confirmation`, `test_rotate_preserves_prior_envelope_on_failed_confirmation`, `test_rotate_preserves_prior_envelope_on_cancelled_confirmation`, `test_create_writes_no_envelope_on_failed_confirmation`, `test_recovery_verify_reports_match_and_preserves_fingerprint`, `test_recovery_recover_rewraps_master_key_and_preserves_fingerprint`, and `test_recovery_recover_refuses_wrong_mnemonic`. Each takes a `tmp_path` fixture and drives a real file provider, so the custody is genuine rather than mocked. Re-run at HEAD for this reconciliation, `uv run --no-sync pytest src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py -m "" -q --no-header` collects 25 tests and reports 25 passed, matching the count the originating record cited; the fifteen further tests in the file are the pre-existing BIP-39 vector and error-registry coverage.

## Notes

Documentation reconciliation only; the tests were not re-authored. The originating record `S76` carries an identical heading and identical scope file, so the map to `S17` is exact. The test run was genuinely executed at HEAD for this record rather than copied from the originating record's cited figure, and the two agree.

The pytest invocation passes `-m ""` deliberately. This project defaults to the `unit` marker, and a bare path invocation can select nothing and still exit zero; forcing an empty marker expression is what makes the 25-collected figure a real measurement rather than a vacuous green.

`RecoveryVerificationError` renders through a translated message key, so its `str()` is empty. The failed-confirmation tests therefore assert on the exception type and on the byte-identical envelope rather than on message text, which is also the correct shape under the project's prohibition on asserting localized prose.

The `date` frontmatter is deliberately the landing date `2026-07-17`, not the reconciliation date `2026-07-25`.

No substantiation gap for this step.
