---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:a836f720b986cffc9ef0d1df46547a9936ecb82f8e5d4433449e65f600b08bc6'
step_id: 'S06'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Land the roundtrip discipline suite for the persisted session (mint, save, fresh-process-shape load, strict model equality with every defaultable field non-default) plus the anti-tautology proofs (corrupt an on-disk deadline byte and assert refusal, delete the keychain entry and assert logged-out treatment, bump schema_version and assert delete-plus-refuse), gate is the new test module green under uv run --no-sync pytest

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_persisted_session_roundtrip.py`

## Description

- Land `test_persisted_session_roundtrip.py`: mint-save-load strict model equality against the real keychain and real files (all record fields required, none defaultable), the no-plaintext-on-disk scan (raw and base64 DEK bytes absent from every persisted file), and the refusal-branch matrix.
- Anti-tautology proofs: editing the persisted idle deadline on disk yields `TAMPERED` (tag break), deleting the keychain entry yields `KEYCHAIN_ENTRY_MISSING` logged-out treatment, bumping `schema_version` on disk yields `SCHEMA_VERSION_MISMATCH` with both artefacts deleted.

## Outcome

Landed in commit `6a0fe2224e`. 29 tests green (`uv run --no-sync pytest .../test_persisted_session_roundtrip.py -q`); full master_key tree 260 green; collect-only clean; apidocs stubs regenerated with `scaffold` and `--check` conformant.

## Notes

No mocks, skips, or xfails anywhere in the suite; the keychain tests run against the live platform backend. A stale zero-byte `.git/index.lock` (25 minutes old, verified held by no process) was removed to unblock the shared index before committing.
