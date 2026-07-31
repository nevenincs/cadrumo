---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:a9f529c640b43238b84a67f69657504dc737963b197b4d9e6caf04ec55a0fcc6'
step_id: 'S02'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove logout preserves provider and certificate-source configuration while clearing real sessions

## Scope

- `src/cadrumo/application/auth/tests/test_operator_storage_session.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S43` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Add one focused real-behavior certificate logout proof against isolated encrypted profile storage.
- Register and select a named certificate source through the public auth facade, persist its passphrase in the canonical secure-storage backend, and save a parseable certificate session through the production session store.
- Snapshot provider selection and configuration time, certificate path, active source, the immutable registration record, and the resolved secret before logout.
- Invoke public `logout_operator_auth` for the certificate provider and prove it removes exactly one persisted session while preserving every configuration and custody snapshot.

## Outcome

The proof exists at HEAD. `src/cadrumo/application/auth/tests/test_operator_storage_session.py`
declares `test_certificate_logout_removes_session_and_preserves_certificate_configuration`,
alongside the four sibling logout proofs the module already carried.

Attribution is a single clean commit: `bee34cf878`, "test(auth): prove
certificate logout preservation", dated 2026-07-16. A content search of the
file's history attributes the test name to that commit and no other, so this
step's delivery is not entangled with any mixed flush commit.

The originating record reports the exact new node passing as one test, the
complete designated module passing as thirteen tests, clean focused Ruff, an
uncached import graph over 3,431 files and 16,260 dependencies with five
contracts kept and none broken, and no production-code change.

## Notes

Substantiated without reservation: the named test node is present at HEAD and
one commit introduced it.

The verification figures quoted above are transcribed from the originating
record and were not re-run for this reconciliation.

The originating record recorded two execution incidents. The mandatory plan-step
dry run exposed collateral serializer output in three unrelated step rows, which
was restored by hand so the final plan diff contained only this step's checkbox
transition. The first feature-scoped vault check reported a scaffold-annotation
warning, resolved by replacing the record body through the owning verb.
