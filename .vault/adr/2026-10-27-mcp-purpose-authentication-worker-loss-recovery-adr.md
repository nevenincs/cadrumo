---
tags:
  - "#adr"
  - "#mcp-purpose-authentication"
date: '2026-10-27'
related:
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-10-12-mcp-parity-attended-live-sign-in-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-reference]]"
superseded_by: '2026-09-26-mcp-purpose-authentication-adr'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:2678aeb44fcd2ba0fecba928cd46e14b551591f866800436425f77cac64fdb78'
---
# `mcp-purpose-authentication` adr: `worker loss session recovery` | (**status:** `superseded`)

Authorized 2026-10-27: the user approved D1 to D7 exactly as drafted, replying "continue, report when both tracks are done" to "Approve all seven as recommended, or change any?". The ruling now lives in the accepted record's "Process containment and custody lifetime" section.

This record is a proposed revision of the accepted `2026-09-26-mcp-purpose-authentication-adr`, section Implementation > "Process containment and custody lifetime". The accepted body stays unchanged until the user authorizes this revision. On approval, the Implementation ruling below is appended to that section, and this proposal is then retired.

## Problem Statement

One profile worker holds the profile DEK and the receipt sealing key in memory only. When the worker is positively lost (contained, exited or its channel closed), `ProfileWorkerSessionOwner` sets `_lost` irreversibly (`src/cadrumo_runtime/host/session_owner.py:405`, `:426`). The next connection sweep then retires every human, attended and API-key session of the profile as `CUSTODY_UNAVAILABLE` (`src/cadrumo_runtime/application/session_authority_core.py:282`).

On 2026-10-27 one worker loss signed the person out of the desktop and also ended the agent's attended session. A transient loss therefore becomes a full sign-out across every surface.

Transient contention no longer causes that. A worker that cannot be observed in time but is not lost keeps every session (`session_authority_core.py:278`).

What remains is to decide whether a positively lost worker can be replaced without forcing every session to restart from nothing, and on what proof.

## Considerations

- The runtime holds no copy of the DEK. A replacement worker can only receive custody through a fresh proof: a password, the human receipt proof, or an API key (`2026-09-26-mcp-purpose-authentication-profile-access-adr`).
- The human receipt is persisted on disk with its key in the OS keychain. It can be resumed by the runtime from a frontend-presented proof without the old worker (`src/cadrumo_runtime/host/profile_receipt.py:31`, `src/cadrumo_client/transport/receipt_proof.py:29`). It inherits its original deadlines and never renews human life.
- Session ids are never portable bearers. Each connection proves itself on its own native connection (`2026-10-04-application-sign-in-adr`).
- Attended children need no grant of their own. Their lineage is bounded by the parent's scope and expiry, and they retire with the parent (`2026-10-12-mcp-parity-attended-live-sign-in-adr`).
- Timeout and process loss never imply rollback. Work in flight at the loss stays `UNKNOWN` and must be reconciled before any retry (accepted section).
- In the incident, a contained worker took 15 to 26 s to exit after job termination. A replacement cannot be ready faster than the old one is reaped.

## Considered options

- **Retire every session on loss (current).** Fail-closed and simple. Rejected as the only behaviour: one transient fault becomes a sign-out of every surface and the agent.
- **Runtime re-shares custody from its own copy.** Fastest recovery. Rejected: the runtime would hold the DEK outside a worker, breaking the custody boundary.
- **Suspend and rebind on fresh proof under the existing session ids.** Chosen. No new custody holder, the same proofs as sign-in, and a bounded window after which the current fail-closed retirement applies unchanged.
- **Suspend and issue new session ids on fresh proof.** Rejected: every client and attended child would need re-admission and new delegation. That gives most of the user-visible disruption of a full sign-out, without any security gain over rebinding on the same native connection.

## Constraints

- The loss of the whole runtime is unchanged. It still invalidates live leases.
- Sign-out, OS lock (on positive evidence), originating OS logout, grant revocation, sign-in generation advance and lease expiry all apply immediately during a suspension. They retire the affected leases exactly as today, and nothing rebinds them.
- A suspended lease grants nothing: no admission, private projection, review response or effect.
- No component other than a worker ever holds the DEK, and nothing persists it beyond the existing custody stores.
- Work that was in flight at the loss is never resumed by rebinding. It stays `UNKNOWN` until it is reconciled.

## Implementation

We will replace irreversible loss with a bounded suspension. The choices below are each decided separately; each states the recommendation. The user's ruling replaces any recommendation it changes.

### D1: Suspension window N

Options:
- 30 s;
- 120 s;
- 300 s.

**Recommendation: 120 s**, measured from the moment the loss is positively established.

- The observed reap time of up to 26 s plus a worker relaunch and receipt resume fits comfortably. That leaves room for a person to retype a password when the receipt is refused.
- 30 s is shorter than the observed reap in a slow case.
- 300 s keeps suspended rows and client retry loops alive longer, which helps nobody once the desktop has shown a password prompt.
- A suspended lease grants nothing, so N is a liveness bound, not an exposure bound.
- A lease whose own deadline passes inside the window retires at that deadline.

### D2: Human rebind proof and identity

**Recommendation:** a human lease rebinds when all of these hold:

- the presenting connection is the same native connection (boot, peer process, frontend, connection id) that held the lease;
- it presents either the profile password or the stored receipt proof;
- the proof is valid for the current sign-in generation and the originating OS login.

On success the runtime:
- starts or reuses the replacement worker;
- installs custody through the existing login path;
- republishes the lease under its existing session id with its original deadlines, never renewed;
- mints a fresh receipt only under the existing post-publication mint rule.

A proof presented on any other connection signs in normally under a new id and does not rebind.

Alternative: allow rebinding from any connection of the same OS login. This is rejected because it would make the session id a portable bearer.

### D3: Attended children

**Recommendation:**
- Attended children never present a proof.
- When their parent rebinds, each child whose own native connection is still open is re-admitted under its existing id, bounded by the parent's scope and remaining expiry.
- A child whose connection closed during the window retires.
- If the parent does not rebind, its children retire with it.

Alternative: require the agent service to re-delegate. That is rejected because it reproduces the disruption this record removes, with no added proof.

### D4: API-key sessions

**Recommendation:**
- An API-key lease rebinds only when its client presents the API key again on the same native connection within the window.
- The runtime keeps no copy of the key to rebind on the client's behalf.
- The grant's current validity, scope and unattended/OS-lock policy are rechecked at rebind.

Alternative: rebind automation from the stored protected unlock material without the key. That is rejected because the key would no longer authenticate the client at the point custody is re-established.

### D5: Fail-closed expiry and repeated loss

**Recommendation:**
- At the end of the window, every suspended lease not yet rebound retires as `CUSTODY_UNAVAILABLE`, with today's semantics.
- If the profile's worker is lost again within 10 minutes of a previous loss, every lease of the profile retires immediately and no new window opens.
- A worker that dies twice in quick succession is treated as crash-looping, not transient.

Alternative: count only a second loss inside the open window. That is rejected because a worker that dies shortly after each recovery would cycle forever.

### D6: Desktop presents its stored receipt automatically

Options:
- automatic;
- ask the person first;
- never (always prompt for the password).

**Recommendation: automatic, once per loss.** The desktop presents its stored receipt proof on its own connection as soon as it observes the suspension of its own human lease.

- Presentation is the same frontend action the application sign-in ADR already permits at start-up, and it renews nothing.
- If the receipt is refused (generation advanced, keychain unavailable, login mismatch), the desktop shows the password prompt for the rest of the window.
- The agent service and MCP children never present the receipt to rebind. They wait for their parent.

### D7: What clients observe while suspended

**Recommendation:**
- Requests on a suspended lease are refused with a distinct typed refusal, `CUSTODY_RECOVERING`, that carries the remaining window.
- The desktop and agent service show a reconnecting state instead of a sign-out, and the CLI reports it as a retryable refusal.
- After the window, the refusal becomes today's `CUSTODY_UNAVAILABLE`.

Alternative: reuse `CUSTODY_UNAVAILABLE` during the window. That is rejected because clients could not tell a recoverable suspension from a final retirement, and the desktop would show a sign-out.

Implementation hypotheses that may change within these constraints:
- the suspension is tracked by the session authority core, not by the worker owner;
- the replacement worker is launched eagerly at loss, without custody, so rebinding is fast.

## Rationale

Rebinding on the same native connection with a fresh proof adds no new holder of custody. It accepts no proof that sign-in would not accept, and it never turns a session id into a bearer. It removes the user-visible consequence of a transient worker fault.

The window and the repeated-loss rule keep the outcome fail-closed. A worker that cannot recover in time, or keeps failing, ends in exactly today's retirement.

## Consequences

- A single worker loss no longer signs the person out or ends the agent's attended session, provided the desktop's receipt is accepted or the person retypes the password within the window.
- In-flight work at the loss still needs reconciliation; recovery does not make it retryable.
- New surface to test:
  - suspension state;
  - rebind on the same connection only;
  - re-admission of children;
  - window expiry;
  - the repeated-loss rule;
  - the new refusal across desktop, agent service, CLI and TUI.
- Reconsider if a platform cannot report the reaping of a contained worker within the window. In that case the replacement could race the old worker's storage handles.
