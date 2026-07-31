---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:9750315751623016266aa41f7e411f9b635d98cd869304da7f62cda45bc1f5df'
step_id: 'S04'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove provider and all-provider deletion leave unrelated bucket session files byte-identical

## Scope

- `src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S45` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Add two real-behavior tests proving a provider-scoped logout and an all-provider reset in one bucket leave an unrelated bucket's on-disk session storage byte-for-byte identical.
- Create two independent profiles, each with the certificate provider configured and a real persisted browser session in its own encrypted bucket storage.
- Fingerprint the unrelated bucket's entire on-disk directory tree, run the auth deletion in the first bucket, and assert the unrelated tree hash is unchanged while the first bucket's own session was actually removed.
- Reconfirm the unrelated bucket's session still resolves after the operation.

## Outcome

Both proofs exist at HEAD.
`src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py`
declares `test_provider_logout_leaves_unrelated_bucket_session_bytes_identical`
and `test_all_provider_reset_leaves_unrelated_bucket_session_bytes_identical`,
alongside the six prior path-composition tests, for eight nodes in the module.

Attribution is a single clean commit: `b8bc13c6b2`, "test(auth): prove
provider/all-provider deletion leaves unrelated bucket session bytes identical",
dated 2026-07-17. A content search of the file's history attributes the test
names to that commit and no other.

The originating record reports the focused module passing at eight tests with
clean Ruff, using real isolated profile storage roots, real encrypted
secure-object session persistence, and the real `logout_operator_auth` and
`reset_operator_auth` services with no mocks.

## Notes

Substantiated without reservation: both named test nodes are present at HEAD and
one commit introduced them.

The verification figures quoted above are transcribed from the originating
record and were not re-run for this reconciliation.

The originating record notes that sessions persist as encrypted secure objects
inside each bucket's own storage, so the byte-identity claim is expressed as an
unchanged fingerprint of the unrelated bucket's whole on-disk tree rather than a
single named file, and that the wizard catalogue import is required in the test
module to seed the profile-key registry before minimal profile registration. No
source change was required.
