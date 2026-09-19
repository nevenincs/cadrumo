---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:96fa60a8a71132c66ff0a0d7c1404c4bf6199ae0b053871d1e64b61f9a08fc0c'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `tui-architecture` reference: `pre custody login secret submission`

## Summary

The existing supervisor has one durable encrypted-operand path and cannot safely
register a profile login before the password opens custody. This reference fixes
the implementation boundary for an operation-owned transient secret channel:
the durable request is credential-free, the secret is exact-bound and consumed
only from process memory, and restart before that consumption is a terminal
interruption before any executor effect.

`OperationSupervisor.submit` serializes every submitted request through
`OperationSecureReferenceStore.put`, writes its returned content digest into
the persisted snapshot, and `start` resolves that reference before building the
executor request (`src/cadrumo/application/operations/_supervisor.py:119-205`).
The same storage path is used when a resumable executor is reconstructed
(`src/cadrumo/application/operations/_supervisor.py:782-807`). Therefore a
`SecretStr` or passphrase-bearing operation request would be persisted before
the login executor runs; declaring `SECURE_REFERENCE` does not change that
runtime behavior (`src/cadrumo/application/operations/_capabilities.py:28-35`).

The concrete secure-reference adapter is intentionally unsuitable for a profile
password. It requires an injected encrypted `SecureObjectRepository` and only
permits identity, financial, or audit classifications
(`src/cadrumo/adapters/persistence/operations/_secure_refs.py:19-64`). The
canonical profile repository is available only for the current matching session
or from a caller already holding the target DEK for a temporary session
(`src/cadrumo/application/user_profile/_custody_ports.py:1123-1172`). Before
login neither condition exists. Reusing either path would be circular, would
persist a secret, or would create a second unlock authority.

The current `login_profile` authority already protects the effect boundary:
target and throttle preflight precede password work, successful proof creates
candidate-only session state, and promotion is the later handover
(`src/cadrumo/application/user_profile/_login_session.py:981-1057`). Its
callback is a current CLI acquisition adapter, not an operation identity
(`src/cadrumo/entrypoints/cli/_config/_custody.py:187-247`). The registered
executor must call that existing authority once after an operation-owned
one-shot secret acquisition; it must not first call login outside the
supervisor or persist a callback reference.

Treating login as ordinary `EPHEMERAL` work cannot avoid the storage problem:
that durability permits only effect `NONE`, no durable replay, and no conflict
scope (`src/cadrumo/application/operations/_capabilities.py:62-75`), while a
successful login changes the active session and pointer. `RECORDED` operation
definitions must permit `UNKNOWN` for owner-loss reconciliation
(`src/cadrumo/application/operations/_registry.py:112-128`). Existing
reconciliation records a merely created operation as recovered, whereas an
unconsumed transient secret cannot be recovered after process loss
(`src/cadrumo/application/operations/_supervisor.py:690-736`). The new channel
therefore needs an explicit pre-effect, non-resumable restart rule rather than
silently inheriting created-operation recovery.

The accepted interface contract already demands an operation-owned public
`EphemeralSecretSubmission` capability with exact operation/interaction binding,
expiry, single use, duplicate and mismatch refusal, cancellation, cleanup, and
non-retention proof, but deliberately leaves its placement undecided
(`.vault/adr/2026-08-11-tui-interface-adr.md:176-199`,
`.vault/adr/2026-08-11-tui-interface-adr.md:435-453`). The operation ADR owns
the missing generic capability; frontends must neither embed callbacks in an
operation envelope nor gain a second lifecycle authority
(`.vault/adr/2026-08-11-tui-architecture-adr.md:132-221`).
