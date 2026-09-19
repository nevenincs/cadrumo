---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:207d6eb8e470c2045f11c0ee2c4bd034820fda6495afe1aa518852a6bee0a942'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-architecture-pre-custody-login-secret-submission-reference]]"
---

# `tui-architecture` audit: `ephemeral secret submission code review`

## Scope

Independent read-only review of `W03.P08.S114` against ADR decisions `D3a`,
`D10`, and `D13`, its pre-custody research and reference, and the current
implementation diff. The review covered the generic credential-free request
registry and journal path; supervisor-owned `EphemeralSecretSubmission`; exact
operation, definition, subject, interaction, and revision binding; expiry,
single-use, mismatch, and duplicate refusal; zeroisation and non-retention;
cancellation, settlement, and shutdown cleanup; pre-entry and post-entry restart
classification; facade and package ownership; absence of login-specific policy,
active-profile inference, compatibility shims, re-exports, and duplicate homes;
and focused real-filesystem lifecycle proof. Focused verification completed with
192 passing operation-platform and persistence tests plus a clean Ruff check.

## Findings

### secret-cleanup-serialization | high | Cleanup can finish before a stale or post-shutdown submission reintroduces the secret

`OperationSupervisor.submit_ephemeral_secret` validates a snapshot and then
mutates `EphemeralSecretBroker` without sharing the operation lease lock or a
supervisor-closed state with cancellation, terminal settlement, and shutdown.
Consequently, a concurrent submission can pause after reading `CREATED`, allow
`request_cancel` to discard the broker entry and durably settle `CANCELLED`, and
then resume and install the secret into the broker after cleanup has completed.
A direct post-shutdown submission is also accepted because `shutdown` only calls
`EphemeralSecretBroker.close`; it does not close the port. The retained secret can
then be consumed by `start`, and the supposedly shut-down supervisor completes
the operation successfully. Both behaviors were reproduced against the real
filesystem adapter. This violates the required zeroisation on cancellation,
terminal settlement, and supervisor shutdown, and leaves a runtime secret in
custody after the durable operation has stopped awaiting it.

Reverification after remediation confirmed that broker access is lock-protected,
shutdown permanently closes the submission channel, and cancellation and
terminal settlement now discard under the same per-operation ordering boundary
used by submission. The original concurrent submission/cancellation reproduction
now settles `CANCELLED`, zeroises the caller buffer, and retains no broker entry;
post-shutdown resubmission is refused and zeroised. The four focused integration
tests pass and Ruff is clean. The finding remains open only because the committed
suite still exercises cancellation sequentially: it contains no deterministic
stale-submission race for cancellation or terminal settlement, and no proof that
shutdown zeroises a buffer already in the broker's active-consumption set. Those
regressions could therefore remove the synchronization or active-buffer cleanup
without reddening the focused conformance suite.

Final reverification resolves this finding. The committed real-filesystem suite
now uses the production per-operation lock as a deterministic barrier for both
submit-versus-cancel and submit-versus-terminal-settlement interleavings. Each
case proves submission waits at the shared boundary, the terminal transition
wins without executor entry, caller storage is zeroised, and no broker entry
survives. A separate live-executor case shuts down while the executor holds the
consumed memoryview and proves its active backing buffer is zeroised before the
executor resumes. The complete focused integration module passes all seven
tests and Ruff is clean. The implementation and regression evidence now satisfy
`secret-cleanup-serialization`; no blocker remains from this finding.

## Recommendations

- Resolve `secret-cleanup-serialization` by making durable liveness validation,
  broker insertion, and cleanup mutually ordered under one supervisor-owned
  operation synchronization boundary, and make shutdown permanently close the
  submission port. Add deterministic race tests proving cancellation and
  settlement cannot be followed by stale insertion, plus a test proving every
  post-shutdown submission is refused while its caller buffer is zeroised and no
  executor can start through the closed supervisor.
