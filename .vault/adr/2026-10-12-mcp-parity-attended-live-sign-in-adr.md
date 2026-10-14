---
tags:
  - '#adr'
  - '#mcp-parity'
date: '2026-10-12'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:b60acebc22c2de51354ff6eea2b89cbd0f9fd43d4a36b18019d54c6f9c5431fd'
related:
  - "[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]"
  - "[[2026-10-10-mcp-parity-shared-sign-in-door-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-10-12-runtime-manager-architecture-caller-owned-root-adr]]"
  - "[[2026-10-12-live-agent-evaluation-adr]]"
  - '[[2026-10-10-mcp-parity-sign-in-doors-reference]]'
  - '[[2026-10-04-application-sign-in-reference]]'
---

# `mcp-parity` adr: `MCP follows an operator-held live sign-in by attended delegation, without a persisted credential` | (**status:** `accepted`)

## Problem Statement

An unattended test harness on a logon without a usable native credential store cannot admit the packaged MCP server into a profile. On such a logon, Windows Credential Manager answers every read with Win32 error 1312, which is what an SSH logon gets. The harness can create the profile and authenticate through the CLI's protected secret channel, but MCP cannot follow that authentication. The operator, 2026-10-12, asked for the runtime to retain a live authenticated session, admit the agent's MCP connection into the same profile, enforce the normal permissions, approval gates, expiry, lock and logout, and end access when the session or the owned runtime ends. The password must stay outside the agent and the model provider. The `session` tool and MCP password sign-in must not return. Knowledge of a profile id, storage path or endpoint must not count as authorization, and not every process that can reach the runtime may be admitted.

## Considerations

The live sign-in depends on a persisted credential today, because:

- **A session belongs to one connection.** A password login admits one human session for the connection that presented the password (`SessionAuthorityAdmission.admit_human`, `src/cadrumo_runtime/application/session_authority_admission.py:281`). When that connection closes, the runtime retires its authority (`RuntimeProfileConnections.disconnect`, `src/cadrumo_runtime/host/profile_connection_sessions.py:359`). So the CLI's session ends when `aeat config login` exits.
- **The shared sign-in is the receipt.** The only thing that outlives the login connection is the receipt, minted after publication (`ProfileWorkerHumanLogin.mint_receipt`, `src/cadrumo_runtime/host/profile_login.py:201`). Its key lives in the OS keychain. Another process follows the sign-in only by reading that key and presenting it (`RuntimeFrontendClient.resume_receipt`, `src/cadrumo_client/transport/frontend_client.py:296`). `2026-10-04-application-sign-in-adr` makes the receipt the runtime-owned shared sign-in, and "no surface keeps login state" (`2026-10-10-mcp-parity-shared-sign-in-door-adr`).
- **Logout needs the receipt too.** `config logout` signs out through a session on its own connection, and gets one only by resuming the receipt (`human_sign_out`, `frontend_client.py:378`). With no receipt it is refused as unproven. A live, non-persisted session has no way to be ended from outside.
- **The two capabilities are therefore one.** "Live" and "persisted" coincide: without the keychain there is no cross-process live sign-in at all.

What already exists and covers the gap:

- The accepted access record defines attended agent access: "Explicit delegation tied to a valid human authorization", with "access ending no later than that authorization". It also defines "Request, inspect, approve or decline delegation" as typed request and decision commands with "exact connection/scope-bound consent" (`2026-09-26-mcp-purpose-authentication-profile-access-adr`, capability matrix and parity table). It records that attended delegation "remains defined and is not used by the MCP server".
- The authority already issues such children (`SessionAuthorityAdmission.delegate`, `session_authority_admission.py:501`). The child goes to a separately verified recipient connection, with kind `ATTENDED` for a human parent. Its scope is the intersection with the parent's, and its expiry is clipped to the parent's remaining budget. It is shared under the parent, so the parent's disconnect cascades (`test_child_scope_and_budget_are_narrowed_and_disconnect_cascades`, `src/cadrumo_runtime/application/tests/test_session_authority.py:472`). It is wired to no runtime request, and today it requires an automation grant.

## Considered options

- **Attended delegation from an operator-held live session.** Recommended. The operator authenticates by password on the CLI's protected channel and keeps that connection open. Each MCP connection that asks to follow the sign-in is shown to the operator with its verified native peer. Only an approved connection receives an `ATTENDED` child of the operator's session. No credential is kept, written or delivered. The profile DEK stays resident only while sessions live, as today.
- **A runtime-held live sign-in followed by any same-user, same-logon connection.** Rejected. It admits every same-user process that can reach the runtime, which the operator forbade. It also keeps the DEK resident beyond any live connection, for up to the sign-in's absolute lifetime. This is the "runtime memory" option `2026-10-04-application-sign-in-adr` left open for receipt extension; it is not needed here.
- **Deliver a key or ticket to the MCP process at launch** (for example `--credential-fd`). Rejected. The operator asked for no new key-delivery mechanism to be assumed. It also moves a bearer secret into the agent-side process.
- **Restore MCP password sign-in or the `session` tool.** Rejected by the operator and by `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`.

## Constraints

Proposed binding commitments:

1. **The operator holds the live sign-in.** The canonical runtime command is `cadrumo-runtime session hold --profile-id UUID`. A verified packaged desktop parent may resume the receipt. The explicit `--password-stdin` path is non-persisted and requires the generic runtime-owned development-root marker plus native peer and password proof. It reads one bounded u32-length-prefixed raw password frame, wipes the mutable buffer, and then accepts bounded correlated JSON decision lines on standard input. Readiness and replies are non-secret JSON with the exact session and connection coordinates. The held session has the existing fixed idle and absolute deadlines; passive status, service traffic and tool calls never extend them. Direct `aeat config login`, `aeat config logout` and profile creation remain tax commands. This replaces the earlier AEAT command and password-channel hypotheses under the operator's 2026-10-14 separation directive.
2. **An MCP connection asks to be attended; it never authenticates.** When `cadrumo-mcp` has no configured key and no receipt to resume, it asks the runtime to attend its existing verified connection to the selected profile. The request carries no secret and grants nothing. The runtime records it with the connection's native peer facts: process id, image path, OS owner, frontend MCP, and the served surface. It refuses the request when no live held sign-in exists for that profile. The request expires after a short bound, and pending requests per profile are capped.
3. **Only the operator's explicit decision admits.** The holder reports each pending request on standard output, with its request id and verified peer facts. It approves or declines one exact request id read from standard input. Approval calls the authority's delegation for that exact recipient connection:
   - The child is `ATTENDED`, has scope parent ∩ served surface, and expires no later than the parent.
   - MCP activity does not extend the parent's idle deadline.
   - Delegation from a human parent needs no automation grant. The constraints of `2026-09-26-mcp-purpose-authentication-profile-access-adr` still apply: no broader scope or expiry than the parent, and cascading revocation.
   - Nothing else changes: a profile id, a storage path, an endpoint or a request id confers no authority, and an unapproved connection receives nothing.
4. **Termination is explicit and verifiable.** A child ends when any of the following happens:
   - its MCP connection closes;
   - the holder's standard input closes or the holder exits, which retires the parent and cascades;
   - the holder is told to sign out, which is a profile-wide human sign-out;
   - `config logout` runs from another process, which authenticates by password on its leaf `--secrets-stdin` channel when no receipt can be resumed;
   - the profile is locked;
   - the idle or absolute deadline passes;
   - the runtime stops.

   In each case later MCP calls are refused with the existing typed results. Nothing is written to the keychain or to storage by this flow.
5. **What MCP may do is unchanged.** Every operation still goes through the normal operation authority, the served surface and the human review gates. An operation needing review still waits for an operator response through the supported CLI or TUI review interface. No secret enters any MCP tool argument or result.
6. **Amendments.**
   - `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr` constraint 2 gains a third door: attendance by an operator-held live sign-in, approved per connection.
   - `2026-10-10-mcp-parity-shared-sign-in-door-adr`: its "delegated child — not chosen" option becomes the chosen door for the attended case only. Receipt resume stays the default.
   - `2026-09-26-mcp-purpose-authentication-profile-access-adr`: attended delegation becomes used by the MCP server, with a human parent needing no grant.
   - `2026-10-04-application-sign-in-adr`: "at most one live human sign-in, persisted as the receipt" is refined. A held sign-in is a live human sign-in of the same single profile that is not persisted. Its `config logout` accepts a leaf password proof when no receipt can be resumed.

## Implementation

If approved, we will:

- add the runtime requests for attendance, pending inventory and decision, plus the hold lifetime;
- wire them to `SessionAuthorityAdmission.delegate` with the human-parent rule;
- add the CLI hold command and the leaf-proven logout;
- add the MCP attendance path in `src/cadrumo_harness/mcp/runtime_adapter.py` and `runtime_admission.py`;
- add the locale keys in every supported locale;
- add unit and integration tests through the real runtime;
- extend `dev/runtime_lifecycle/caller_owned_root.py` to prove the whole flow on the rebuilt package.

Hypotheses that may change within the constraints:

- the command name;
- the request expiry and cap;
- the JSON event field names;
- whether `sign-in-status` reports a held sign-in as its own presence value.

## Rationale

The accepted access record already names attended delegation as the way an agent works under a person's live authority, and the authority already enforces it. The operator's held connection is the live sign-in, so following it needs no stored credential, and persistence stays an independent feature. Per-connection approval of a verified native peer means that only the processes the operator chose are admitted. Ending the held connection ends every child through the cascade the authority already has, which gives a live, non-persisted session a precise termination.

## Consequences

- A headless harness can run the real package with authenticated MCP on any logon, with no keychain, and without the password reaching MCP or a model.
- The operator, or a harness acting as the operator, must keep one process open for the whole run, and must approve each MCP connection. A crashed harness ends access, which is intended.
- Same-user processes can create attendance requests. They grant nothing, are capped and expire, and the operator sees each request's verified process before deciding.
- Desktop persisted sign-in and its verification are unchanged and stay a separate integration requirement.
- Accepted 2026-10-12 on the operator's first-hand approval of this text ("Approve as proposed"). Acceptance records the decision; implementation and verification are reported separately.

## Amendments

Amended 2026-10-12 on implementation, within the operator's approval of this record. The rest of the record stands. The changes:

- **Command and password channel (constraint 1).** The hold command is `cadrumo-runtime session hold --profile-id UUID --password-stdin`, beside `config sign-in-status`. It reads the password once as the first line of standard input, a strict JSON object `{"passphrase": "..."}` parsed by the command line's existing machine-secret parser, rather than from `--secrets-fd`. A descriptor that a Windows parent must pass by handle inheritance was not a portable channel for a harness. The rest of standard input carries one decision object per line, and standard output carries one JSON event per line, followed by the result.
- **Timing (constraints 2 and 3).** The bounds are recorded:
  - an ask lapses after 120 seconds unanswered;
  - at most 8 asks per profile wait at once;
  - one MCP call waits at most 90 seconds for a decision;
  - an attended child is a short lease, at most the five-minute maximum of any delegated lease, and is issued again without a new decision to the same approved connection while the parent session lives;
  - a holder counts as present only while its own connection holds the human session it named when it last listed the asks.
- **Attended sessions are not automation sessions.** Lease revalidation, status and the operation guard judge an attended child of a person's session by its lineage, without consulting automation custody, wherever no grant names it. Leaving the periodic revalidation unchanged retired every attended child where the native credential store was unavailable. The packaged proof found this on a remote-shell logon.
- **Disclosure destination.** On approval the attended connection takes the holder's client identity as its disclosure destination, so the child's disclosures are the person's own. The child remains a distinct session on its own connection.
- **Status.** The MCP `status` tool reports an attended session as `"session": "attended"`.


Amended 2026-10-14 under the operator's runtime separation directive: held sign-in and all authentication administration beyond direct AEAT profile login, logout and creation belong to `cadrumo_runtime`. The host and client API are separate canonical packages with no tax/client import of the host. The earlier 2026-10-12 command-channel refinement is history; the current holder uses the bounded native password frame and correlated decision grammar above. No AEAT hold alias remains. Runtime authority still requires exact native peer proof, current parent authorization and cascading retirement; a marker or known profile alone grants nothing.
