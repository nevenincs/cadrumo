---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove certificate secrets set, resolve, and remove only through real secure storage, force real event-commit failure after set and remove, prove retry resumes the original operation and emits the original stable event exactly once, and prove no certificate keyring backend, selector, fallback, migration, probe, or parallel secret writer remains

## Scope

- `src/cadrumo/application/auth/tests/test_certificate_secret_backend.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S51` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Prove certificate secrets set, resolve, and remove only through real encrypted secure storage, scoped by bucket, with no keyring path.
- Force a real event-commit failure after set and after remove and prove a secret-free durable intent survives.
- Prove a retry resumes the original operation, emits the original stable event exactly once, preserves the set versus rotated classification, and reports removal truthfully.
- Prove no certificate keyring backend, selector, fallback, migration, probe, cleanup path, or parallel secret writer remains.

## Outcome

Both proof modules exist at HEAD and carry the asserted nodes.

`src/cadrumo/application/auth/tests/test_certificate_secret_backend.py` declares
sixteen tests covering roundtrip, unset absence, rotation on re-set, idempotent
removal, per-bucket scoping, repr non-leakage, and a stable secret-free request
witness, plus the operator-level set, resolve, and remove paths including the
proof that a set result never carries the secret and that a second set reports
rotation. Its absence gates are
`test_retired_keyring_symbol_absent_from_backend_module`,
`test_retired_keyring_symbol_absent_from_auth_facade`, and
`test_secure_storage_backend_is_the_only_public_backend`.

`src/cadrumo/application/auth/tests/test_operator_transaction_recovery.py`
declares the three certificate-secret recovery proofs by name:
`test_certificate_secret_set_event_failure_resumes_original_set_once`,
`test_certificate_secret_rotation_event_failure_resumes_original_rotation_once`,
and `test_certificate_secret_remove_event_failure_reports_original_removal_once`.
It further declares the fail-closed guards a pending cleanup must impose:
`test_pending_cleanup_refuses_new_auth_configuration_source_and_secret_writes`,
`test_pending_cleanup_refuses_central_live_session_writer`, and
`test_failed_reset_serializes_and_refuses_concurrent_central_session_writer`,
alongside the logout and reset resumption proofs and the real revision-conflict
and concurrent-writer regressions.

Delivery is attributable to two focused commits that touch both files:
`f5273bda59`, "refactor(auth): unify certificate credentials on secure storage;
delete keyring backend", which added the absence gates and the first parity
coverage, and `27d8bc5404`, "fix(auth): make certificate secret mutations
resumable", which added the recovery proofs. The serialization commit
`1a8ee75547` also contributed to the recovery module. The originating record's
third cited commit, `84c435bb94`, is the CLI-level recovery proof and belongs to
the sibling step rather than to these two modules.

The originating record reports both files green within a ninety-nine-test
focused application auth run.

## Notes

Substantiated. The named test nodes are present at HEAD and two focused commits
with matching subject lines carry them.

Two later commits revised these modules after the step landed: `009ed60006`,
which deleted a secret-store test seam in favour of real dependency injection,
and `c4a8166ab4`, which dropped the vestigial backend descriptor and added the
assertion that the descriptor is absent. Both tighten the surface in the
direction this step intended.

The verification figures quoted above are transcribed from the originating
record and were not re-run for this reconciliation. In particular, this record
does not independently confirm that the suites are green at the current HEAD; it
confirms that the asserted proof nodes exist and that their delivery commits
resolve.
