---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:dd3d2fd434b5be282dd14d92b3eb5247d7b0eb0af2f97833ed1e48f9e86fa344'
step_id: 'S45'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove provider and all-provider deletion leave unrelated bucket session files byte-identical

## Scope

- `src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py`

## Description

- Add two real-behavior tests proving a provider-scoped logout and an all-provider reset in one bucket leave an unrelated bucket's on-disk session storage byte-for-byte identical.
- Create two independent profiles, each with the certificate provider configured and a real persisted browser session in its own encrypted bucket storage.
- Fingerprint the unrelated bucket's entire on-disk directory tree, run the auth deletion in the first bucket, and assert the unrelated bucket's tree hash is unchanged while the first bucket's own session was actually removed.
- Reconfirm the unrelated bucket's session still resolves after the operation.

## Outcome

Focused suite green: `uv run --no-sync pytest src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py -q` reports 8 passed (6 prior path-composition tests plus the two new cross-bucket byte-identity proofs). Ruff clean. The tests use real isolated profile storage roots, real encrypted secure-object session persistence, and the real `logout_operator_auth` / `reset_operator_auth` services with no mocks.

## Notes

Sessions persist as encrypted secure objects inside each bucket's own storage, so the durable byte-identity claim is expressed as an unchanged fingerprint of the unrelated bucket's whole on-disk tree. The wizard catalogue import is required in the test module to seed the profile-key registry before `register_minimal_profile`. No source-code change was required; only the missing proof was added.
