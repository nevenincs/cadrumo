---
tags:
  - '#research'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:8fa9cd75ece084bbff0cfba388f197305eac1120977e3a085209ff9e3fc509e3'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `tui-architecture` research: `pre custody login secret submission`

Profile login is the only S39 operation whose password must be accepted before
any profile DEK exists. The current supervisor cannot represent that intent
without persisting the password or requiring the session login creates. The
evidence favors a generic, credential-free durable request identity plus a
separate supervisor-owned one-shot secret submission port; the operation ADR
must settle its exact model, state transition, and API before profile-login
registration can begin.

## Findings

### The current operation contract has no safe pre-custody request path

`submit` persists every request through the injected secure-reference store
before it creates the lifecycle record, and `start` resolves that same stored
payload before executor entry. The secure-reference sensitivity declaration is
metadata only; it does not select a different storage path. Its production
adapter requires an encrypted repository and excludes secret classification.
The profile-custody repository can open without the ambient session only when
the caller already has the target DEK. Thus a passphrase-bearing login request
is circular before the password proof, while a non-secret request stored in
the present secure store is also unavailable. `src/cadrumo/application/operations/_supervisor.py:119-205`
`src/cadrumo/application/operations/_capabilities.py:28-35`
`src/cadrumo/adapters/persistence/operations/_secure_refs.py:19-64`
`src/cadrumo/application/user_profile/_custody_ports.py:1123-1172`

### The existing operation choices do not resolve the secret boundary

An `EPHEMERAL` operation may declare only `NONE` effect, no durable replay, and
no conflict scope, so it cannot honestly represent a successful profile
handover. A recorded operation must permit `UNKNOWN` owner-loss effect; its
current reconciliation treats an unstarted created record as recovered rather
than terminal. The ordinary response contract is also unsuitable: it carries
only apply/reject decision fields and hashes its entire response into durable
continuation evidence. Putting a password in either the request or a response
would violate the accepted secret exclusion. `src/cadrumo/application/operations/_capabilities.py:62-75`
`src/cadrumo/application/operations/_registry.py:112-128`
`src/cadrumo/application/operations/_supervisor.py:690-736`
`src/cadrumo/application/operations/_interactions.py:47-172`
`.vault/adr/2026-08-11-tui-architecture-adr.md:91-94`

### A separate secret port is narrower than a secure specialization of respond

The accepted interface ADR already requires an operation-owned public
`EphemeralSecretSubmission` with exact operation and interaction binding,
expiry, single use, duplicate/mismatch refusal, cancellation, cleanup, restart
behavior, and non-retention proof. It intentionally leaves whether this is a
specialized response or a separate port undecided. The current response model's
durable proof makes a separate port the smaller compatible direction: it can
accept only ephemeral bytes plus the safe binding tuple, while the envelope,
journal, events, receipts, and frontend-facing interaction remain secret-free.
The ADR must still specify whether the durable safe requirement is a new
interaction variant or a sibling state field. `.vault/adr/2026-08-11-tui-interface-adr.md:176-199`
`.vault/adr/2026-08-11-tui-interface-adr.md:435-453`
`src/cadrumo/application/operations/_journal.py:22-58`

### Restart before secret consumption can be classified more narrowly than restart after login entry

The durable record can safely identify a pre-effect secret wait when it contains
only the non-secret target and an expired/unsatisfied secret requirement. On a
new process the in-memory broker is empty, so reconciliation can terminally
interrupt that state with `effect=NONE` before the login executor is called.
After the executor crosses into `login_profile`, current generic owner-loss
reconciliation remains the honest `UNKNOWN` path unless its custody handover
has an authoritative committed outcome. This split avoids either resuming from
a lost password or falsely claiming no effect after an entered handover.
`src/cadrumo/application/user_profile/_login_session.py:981-1057`
`src/cadrumo/application/operations/_supervisor.py:738-852`

### The durable pre-DEK login target must be a typed credential-free request

Current login resolves its target and throttle before password proof, then
constructs only candidate session state until promotion. The profile target is
therefore a safe, exact operation subject/request independent of the password.
The smallest generic storage extension is a strict credential-free request
policy, serialized atomically with the lifecycle journal and content-digested
for idempotency, alongside the existing encrypted-reference policy for
confidential operands. Deriving it later from an active-profile store would be
circular; deriving it ad hoc from `subject_ref` would create a login-only
executor exception. `src/cadrumo/application/user_profile/_login_session.py:920-1057`
`src/cadrumo/application/operations/_models.py:63-107`
`src/cadrumo/application/operations/_journal.py:22-121`

### Existing custody and auth authorities remain composition targets

The registered auth executor can invoke public `application.user_profile`
login and passphrase-rotation authorities, but must not move their custody,
candidate-session, or handover code into `application.auth`. Auth storage
surfaces already require a serving custody session and explicitly refuse a
target that cannot be opened without its password. Existing CLI login obtains
the value at the transport boundary through an explicit channel, then passes a
callback directly to the authority; a registered path must replace that
callback-as-identity without adding a second login. `src/cadrumo/application/auth/_operator_scope.py:149-199`
`src/cadrumo/entrypoints/cli/_config/_custody.py:187-247`

### Alternatives bounded by this research

- Persist the password in the existing secure-reference store: rejected; it is
  unavailable before custody and lacks a secret classification.
- Make login a generic ephemeral operation: rejected; its declared effect and
  replay constraints contradict successful login.
- Add a profile-login exception that reconstructs request state from the
  subject: rejected; it forks the generic request contract and leaves no
  canonical pre-DEK storage rule.
- Smuggle a frontend callback, token, or secret into the envelope or ordinary
  response: rejected; it violates the operation and interface secret boundary.
- Start login outside the supervisor and wrap its result afterwards: rejected;
  it creates the second lifecycle authority the operation ADR prohibits.

This research did not select byte representation or process-memory zeroisation
mechanics for the broker; the ADR must limit its durable contract and require
runtime-bound custody plus non-retention tests without claiming impossible
whole-runtime erasure.

## Sources

- `.vault/adr/2026-08-11-tui-architecture-adr.md:91-94`
- `.vault/adr/2026-08-11-tui-interface-adr.md:176-199`
- `.vault/adr/2026-08-11-tui-interface-adr.md:435-453`
- `src/cadrumo/adapters/persistence/operations/_secure_refs.py:19-64`
- `src/cadrumo/application/auth/_operator_scope.py:149-199`
- `src/cadrumo/application/operations/_capabilities.py:28-35`
- `src/cadrumo/application/operations/_capabilities.py:62-75`
- `src/cadrumo/application/operations/_interactions.py:47-172`
- `src/cadrumo/application/operations/_journal.py:22-121`
- `src/cadrumo/application/operations/_models.py:63-107`
- `src/cadrumo/application/operations/_registry.py:112-128`
- `src/cadrumo/application/operations/_supervisor.py:119-205`
- `src/cadrumo/application/operations/_supervisor.py:690-736`
- `src/cadrumo/application/operations/_supervisor.py:738-852`
- `src/cadrumo/application/user_profile/_custody_ports.py:1123-1172`
- `src/cadrumo/application/user_profile/_login_session.py:920-1057`
- `src/cadrumo/entrypoints/cli/_config/_custody.py:187-247`
