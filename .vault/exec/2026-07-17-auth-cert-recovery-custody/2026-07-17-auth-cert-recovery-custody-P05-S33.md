---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:6fdcb12c61a8a8a84896983daa4ea934874d317235162ab801af4ebb6eeb7c2d'
step_id: 'S33'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove certificate secret set and remove against real secure storage, including command failure after the secret mutation but before event commit followed by an idempotent retry with one correctly classified event, and reject backend selection, keyring spellings, migration, fallback, and duplicate mutation paths

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py`

## Description

Verified the certificate-secret set/remove proof suite in `_config/tests/test_certificate.py` already exercises every contract this step requires, against the real Typer tree and real encrypted secure storage with no test doubles.

- Confirmed set/remove operate against real secure storage: `test_certificate_secret_set_then_remove_roundtrip` sets, rotates, and removes a passphrase and asserts the secret value never appears in any output line.
- Confirmed the crash-window contract: `test_certificate_secret_set_cli_resumes_failed_event_commit_as_set_once` and the rotation/remove siblings inject a real SQLite trigger that aborts the event-history commit AFTER the secret mutation, prove the durable intent is staged, prove a same-secret retry resumes the original operation and emits exactly one correctly-classified event (`AUTH_CERTIFICATE_SOURCE_SECRET_SET` vs `_ROTATED` vs `_REMOVED`), and prove a mismatched-secret retry refuses.
- Confirmed rejection of backend selection, keyring spellings, migration, fallback, and duplicate mutation paths via `test_certificate_secret_cli_exposes_no_backend_or_legacy_grammar`.

## Outcome

Step satisfied against the current tree with no change to the proof suite. `test_certificate.py` runs green (13 passed) under the serial integration pass (`-n0`). The suite is real-behavior throughout: real profile bucket, real PKCS#12 fixtures, real secure-object storage, and a real SQLite abort trigger to force the mid-operation failure.

## Notes

Verify-and-close: the proof suite was authored alongside the P02 certificate custody backend and already covers the full contract. Recorded under the plan's own feature stem per plan-closure-requires-exec-records. No skip/xfail/mocked event boundary; the failure is forced by a real database trigger.
