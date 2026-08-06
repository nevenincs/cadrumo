---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:99aec326d39ca024a59a589d6ba42e97654dd7092d0e963ea39313b5824fffa2'
step_id: 'S07'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Make the active certificate credential resolver and named-source certificate check use only selected-profile secure storage with explicit fail-closed absence, and make ordinary certificate-secret set and remove crash-resumable through one secret-free durable intent carrying a stable operation id, event kind, timestamp, prior-presence state, and non-secret completion witness

## Scope

- `src/cadrumo/application/auth/_certificate_sources_operator.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S48` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Remove the check-specific global-password fallback and project each named source's secure-storage secret, including explicit absence, into an isolated settings value.
- Reuse one private fail-closed named-secret helper from both the registry check and the active credential resolver so storage-error policy has one declaration.
- Treat real secure-storage read failures as absent named credentials so the health probe fails closed instead of inheriting a global password.
- Persist one secret-free durable intent per certificate-secret mutation, carrying a stable operation id, event kind, timestamp, prior-presence state, and a non-secret completion witness.
- Resume a pending mutation before accepting a new one, without migration, fallback, probing, reconciliation, or a parallel secret writer.
- Rebind the existing valid, expiring, expired, and multi-source health tests to real encrypted per-source secrets, and add adverse coverage where a capable global password must not open a secretless named source.

## Outcome

Both halves exist at HEAD in
`src/cadrumo/application/auth/_certificate_sources_operator.py`.

The durable-intent machinery is present and typed: the module imports
`CertificateSecretMutationIntent`, opens mutations through
`_certificate_mutation_span(resume_certificate_secret=True)` for both the set
and remove paths, and carries `_pending_intent_resumes` to decide whether a
persisted pending intent is the one a call resumes. The intent is built with a
`hashlib.sha256`-derived stable `operation_id`, a
`CertificateSecretMutationEventKind` of `SET` or `ROTATED` chosen from
`prior_present`, and a `request_witness` that is `None` when no secret is
supplied and otherwise a backend-computed witness rather than the secret
itself, satisfying the secret-free requirement.

The fail-closed check is delivered by commit `9dc920909d`, "fix(auth): fail
closed named certificate checks", dated 2026-07-16, which is the prompt-run this
step's originating record describes. The resumable-mutation authority it
preserved rather than rewrote is commit `27d8bc5404`, "fix(auth): make
certificate secret mutations resumable", dated 2026-07-16, with its real CLI
recovery proof in `84c435bb94`, "test(auth): prove certificate secret CLI
recovery". All three commits resolve.

The resumability behaviour is covered by real-behaviour proofs rather than
assertion. `src/cadrumo/application/auth/tests/test_operator_transaction_recovery.py`
declares `test_certificate_secret_set_event_failure_resumes_original_set_once`,
`test_certificate_secret_rotation_event_failure_resumes_original_rotation_once`,
and `test_certificate_secret_remove_event_failure_reports_original_removal_once`,
plus the fail-closed pending-cleanup guards against configuration, source,
secret, and central live-session writers.

The originating record reports the mutation-sensitive missing-secret node
passing as one test, the complete check module passing as thirteen tests, clean
focused Ruff, and directed duplication searches finding exactly one public check
caller, one raw named-secret read seam, one shared fail-closed read-policy
helper, and one secure-storage backend, with no second fallback and no parallel
secret writer introduced.

## Notes

Substantiated. Delivery is spread over three named commits rather than one, but
each is a focused commit with a matching subject line, so attribution is
recoverable without hunk-level reasoning.

The originating record disclosed a real import-linter failure at execution time:
the layered contract was blocked by the newly landed reset work importing a
storage bucket module from the application configuration-reset module. That
failure is outside this step's path set, was reproduced only after the peer
reset commit `60135859e2` landed, and was explicitly not caused by this step,
which removed an application import rather than adding an application-to-adapter
dependency. This reconciliation did not re-run the import graph and therefore
makes no claim about the current state of that contract.

The verification figures quoted above are transcribed from the originating
record and were not re-run.
