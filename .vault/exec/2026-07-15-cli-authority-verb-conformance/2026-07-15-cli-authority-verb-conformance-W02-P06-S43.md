---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S43'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---
# Prove logout preserves provider and certificate-source configuration while clearing real sessions

## Scope

- `src/cadrumo/application/auth/tests/test_operator_storage_session.py`

## Description

- Add one focused real-behavior certificate logout proof against isolated encrypted profile storage.
- Register and select a named certificate source through the public auth facade, persist its passphrase in the canonical secure-storage backend, and save a parseable certificate session through the production session store.
- Snapshot provider selection and configuration time, certificate path, active source, the immutable registration record, and the resolved secret before logout.
- Invoke public `logout_operator_auth` for the certificate provider and prove it removes exactly one persisted session while preserving every configuration and custody snapshot.
- Ground the test with Vaultspec-RAG searches for logout authority, real certificate-secret storage, source selection, and persisted-session behavior, then confirm the live symbols and nearest test analogues with exact searches.

## Outcome

- Added `test_certificate_logout_removes_session_and_preserves_certificate_configuration`.
- The exact new node passed: 1 test.
- The complete designated test module passed: 13 tests.
- Focused Ruff passed with no findings.
- The uncached import graph analyzed 3,431 files and 16,260 dependencies; all five contracts were kept and none were broken.
- The plan structural check reported only the existing intentional non-monotonic Step-order warning.
- The feature index was regenerated and the final feature-scoped Vault check passed every check with no warnings.
- Production code was unchanged.

## Notes

- The mandatory `vault plan step check --dry-run` exposed collateral serializer output: one template annotation block and stray backticks in the unrelated S48, S51, and S118 rows. The required CLI close was executed, then only that collateral text was restored; the final plan diff contains solely the S43 checkbox transition.
- The first feature-scoped Vault check reported the expected scaffold-annotation warning. The record body was replaced through `vault set-body`, and the final check passed after cleanup.
- No test doubles, monkeypatching, skips, xfails, data loss, production edits, or unrelated-path changes were introduced.
