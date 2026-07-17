---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S51'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove certificate secrets set, resolve, and remove only through real secure storage, force real event-commit failure after set and remove, then prove retry resumes the original operation, emits the original stable event exactly once, preserves SET versus ROTATED classification, and reports removal truthfully, and also prove no certificate keyring backend, selector, fallback, migration, probe, cleanup path, or parallel secret writer remains

## Scope

- `src/cadrumo/application/auth/tests/test_certificate_secret_backend.py`
- `src/cadrumo/application/auth/tests/test_operator_transaction_recovery.py`

## Description

- Confirm certificate secrets set, resolve, and remove only through real encrypted secure storage, bucket-scoped, with no keyring path.
- Confirm a forced real event-commit failure after set and after remove leaves a secret-free durable intent, and that a retry resumes the original operation, emits the original stable event exactly once, preserves SET versus ROTATED classification, and reports removal truthfully.
- Confirm no certificate keyring backend, selector, fallback, migration, probe, cleanup path, or parallel secret writer remains.

## Outcome

Verified complete against the committed tree. `test_certificate_secret_backend.py` exercises set/resolve/remove/rotate/scope through a real encrypted `SecretStore` and pins the retired-keyring-symbol absence on both the module and the `application.auth` facade. `test_operator_transaction_recovery.py` injects real SQLite event-commit aborts and proves set, rotation, and removal each resume once with a single stable event, preserved classification, and a secret-free intent, and that pending cleanup fails closed against configuration, source, secret, reset, and central live-session writers. Both files are green in the focused run (part of the 99-passed application-auth suite).

## Notes

The resumable secret-mutation machinery and these proofs landed across commits `f5273bda59`, `27d8bc5404`, and the in-flight freeze snapshots under the W02.P07 credential-unification wave; this step is closed as verified-complete with its real-behavior recovery and absence gates green.
