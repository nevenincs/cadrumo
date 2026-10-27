---
tags:
  - '#reference'
  - '#rust-component-provisioning'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:48f5de50aad23bc3bb6e96abfed9d6ebff77ae8ea7f543572eaa0847d795b2b0'
related:
  - "[[2026-10-26-rust-component-provisioning-registered-operations-adr]]"
---
# `rust-component-provisioning` reference: `Existing operation review authority and human handoff boundary`

Static code research for the pending human-review authority choice. Source baseline: Git commit `1dbc9466fb`; the named authority modules were inspected in the shared working tree and their defining guards were checked against that commit. Concurrent S01 component cancellation work is outside this record. No runtime, native race, integration or security test was run for these findings.

## Summary

The accepted registered-operations ADR permits MCP to start and observe `config.provision.setup` while a person answers its REVIEW on CLI, TUI or desktop. Existing operation management deliberately permits only the original submitter to use its response capability. The missing piece is an authorized transition from retained invocation capability to a separately verified human response actor. Observation, reattachment and session attendance do not supply that transition.

## Existing authority chain

- `src/cadrumo_runtime/host/operation_host.py:797`: `manage` requires `actor_ref` to equal the current session, the submitting session to be the current session, and the original submission to retain a response capability. Its control path states that a fresh session, replayed receipt or reattachment cannot obtain the original capability. This is a deliberate authority boundary, not a frontend display defect.
- `src/cadrumo/application/operations/_projection_authority.py:86`: the process-local response broker reserves one actor-bound capability, retains the issued checkpoint/token under a lock, checks capability, actor, operation, interaction, revision, expiry and pending-checkpoint equality, then transfers the token once into a bound response service. The existing broker has no authorized human reassignment method.
- `src/cadrumo/application/operations/projection_services.py:366`: `OperationResponseCapability` is an opaque process-local handle with production-only issuance and destructive close. `OperationResponseAuthorityBroker` cannot survive restart. `src/cadrumo/application/operations/composition.py:196` gives no-capability callers unavailable response authority; inspection uses the same separately held capability.
- `src/cadrumo/application/operations/interactions.py:115`: a durable pending checkpoint stores the response-token digest rather than the bearer. Response consumption checks exact operation, interaction, revision, continuation, reviewed proposal and apply baseline/effect digests. A consumed checkpoint records the decision and response digest; a separately inspectable human claim/decision attribution would need deliberate journal support.
- `src/cadrumo_client/contracts/operation_access.py:143`: `OperationReview` explicitly projects review content without acquiring response authority. `OperationSubmitted` contains no response capability. `OperationManage` wraps the canonical response/lifecycle requests; adding a human claim would change the typed transport contract.

## Human identity and invocation identity are separate

- `src/cadrumo_runtime/host/profile_connection_operations.py:284`: `_operation_target` checks runtime boot, native peer, draining state, exact connection, profile and session. Existing projection replies additionally pass the profile's authorization fence.
- `src/cadrumo_runtime/host/profile_connection_person_acts.py:1`: the module explains that frontend identity is a client claim. `_refused_as_persons_act` also calls the native `_nonhuman_peer` check, refusing an automation-tree process whatever frontend it names. `src/cadrumo_runtime/host/profile_connection_admission.py:141` applies native nonhuman/person checks during login and verifies desktop holders. Reuse these admission controls; an MCP origin string or client-supplied human label is insufficient.
- `src/cadrumo_runtime/host/operation_authority.py:145`: `execution_caller` deliberately preserves the original automation admitting frontend when another session re-enters. `bind_reentry` at line 291 expressly does not recreate or transfer response capability. Human response attestation must be separate from immutable MCP invocation provenance.
- `src/cadrumo_runtime/host/profile_connection_attendance.py:383`: attended admission binds a specific automation recipient to the holder's parent session. This controls a session's lifetime and scope; it neither transfers an operation REVIEW bearer nor makes every MCP invocation an attended child. Issued profile keys remain an accepted MCP admission route.

## Reusable surfaces and proposed insertion points

`src/cadrumo_runtime/host/session_hold_operations.py:325` already relays desktop review projection. Its `_respond` at line 355 rechecks interaction, revision and the canonical displayed-document digest, then calls the ordinary response control path. `native/desktop/src-tauri/src/agent/person.rs:333` already maps person operation submit, observe, result, review and respond messages. Reuse this verified person transport rather than introducing a second approval broker; it currently still encounters the original-submitter guard.

A bounded claim would need a dedicated request/reply in `src/cadrumo_client/contracts/operation_access.py`, native admission in `src/cadrumo_runtime/host/profile_connection_operations.py`, an attested worker message in `src/cadrumo_runtime/contracts/profile_worker.py:275`, client/dispatch changes in `src/cadrumo_runtime/adapters/profile_worker_operation_client.py:312` and `src/cadrumo_runtime/host/worker_operation_requests.py:514`, and a definition-specific path in `operation_host.py`. The current response broker is the custody owner to extend atomically. These are proposed insertion points, not implemented behavior.

Human CLI/TUI clients need an explicit claim-and-answer action for a known operation. The TUI's existing `src/cadrumo/entrypoints/tui/operations/modal.py` and `interactions.py` should render the exact current review and obtain claim authority before enabling response. The desktop can extend its person relay. General observation, cancellation, detach, replay and execution ownership need no new authority.

## Decision coverage and unresolved choice

`2026-10-26-rust-component-provisioning-registered-operations-adr` constraints 7-8 establish signed-in profile binding and MCP start/observe with human-only approval. `2026-08-11-tui-architecture-adr`, D4, requires a separate exact secure bearer and says fresh-process observation cannot recreate it. `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr` preserves profile-key admission as well as attended/resumed human sign-in. These commitments do not yet choose who may claim a setup review or authorize actor reassignment.

Option A is an explicit provisioning-only claim by a verified HUMAN session on the same exact active profile while the original invocation lease remains live. Any such authorized human session is recommended: a parent-only predicate would exclude secondary CLI/TUI sessions and key-admitted MCP calls without an attended parent. This is an inference and proposal, not current authority. Option B requires the human to submit originally and removes MCP-started setup from the promised behavior; it needs an explicit change to accepted constraint 8.

## Required verification if A is accepted

Exercise the real runtime admission and broker chain: MCP original-submitter claim/inspect/apply/reject refusal; forged person frontend and key-session refusal; separate human same-profile success; wrong profile, boot, generation and lease refusal; concurrent humans with one holder; replay/foreign actor/drift refusal; claimant and invocation retirement fencing; and unchanged original-submitter guards for other definitions. End-to-end setup must reject with NONE, apply exactly the reviewed role plan digest, preserve UNKNOWN on lost apply outcome, and journal MCP invocation provenance separately from the verified human decision. These are verification requirements, not results.

The installed native desktop uses the Rust relay: `native/desktop/src-tauri/src/agent/person/native.rs:13` imports `OperationRelay` from `native/application/src/person_operations.rs`. Its `respond` at line 692 rechecks displayed review digest, inspects `operation_manage` response authority and then mutates it. Extend this Rust relay for the installed desktop; the Python holder remains its canonical probe/attendance analogue.
