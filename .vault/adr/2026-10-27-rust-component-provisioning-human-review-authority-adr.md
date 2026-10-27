---
tags:
  - '#adr'
  - '#rust-component-provisioning'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:a7a8d8b8e9c599b55776dbab6bb838669e09f251e2fd9bbfe8658b0a9924e201'
related:
  - "[[2026-10-27-rust-component-provisioning-human-review-authority-reference]]"
  - "[[2026-10-26-rust-component-provisioning-registered-operations-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]"
---
# `rust-component-provisioning` adr: `Explicit human claim of a provisioning review` | (**status:** `accepted`)

## Problem Statement

MCP is authorized to start and observe component setup, while only a person may answer its REVIEW. The runtime currently gives the original submitter exclusive response capability, so an independently signed-in CLI, TUI or desktop person cannot answer an MCP submission. This amendment supplies one explicit provisioning authority transition. Accepted 2026-10-27 on the owner's explicit choice of A: "Guarded human claim recommended, implement." This authorizes the bounded claim implementation and the reconciliations recorded below; acceptance does not claim that implementation or verification is complete.

Grounding: `2026-10-27-rust-component-provisioning-human-review-authority-reference`, pinned to commit `1dbc9466fb`.

## Considerations

The process-local broker already owns exact checkpoint, actor and single-use bearer custody. The current original-submitter guard deliberately prevents reattachment from acquiring it. A human response actor must be verified independently of the operation's immutable MCP invocation provenance. Existing verified person admission and desktop relay can be reused, but attendance is session authority rather than review handoff. MCP may also be admitted with a profile key and have no human parent session.

## Considered options

- **A: Explicit provisioning-only human claim. Chosen by the owner, 2026-10-27.** Preserve MCP start/observe and let a currently authorized human on the same exact active profile explicitly claim its current REVIEW. This adds a narrow transport/custody transition and retirement/race obligations.
- **B: Human must be the original submitter. Rejected.** Keep current response authority untouched. MCP reports the need for setup or observes a human-started setup. Smaller implementation, but withdraws the accepted promise that MCP may start setup and have a person answer later.
- **Restrict A to the MCP parent human session. Rejected.** Parent binding exists for attended sessions, but excludes independently authenticated CLI/TUI people and profile-key MCP admissions without that parent. It does not fulfill the named surface behavior generally.
- **Infer response authority from observation or transfer generic operation ownership. Rejected.** Neither is needed for the task, and both cross existing secure response and lifecycle boundaries.

## Constraints

Binding commitments:

1. Only the pending REVIEW of `config.provision.setup` is claimable. Every human responder, including an original human submitter, explicitly claims that current review before inspecting response authority or answering it. This gives setup one verified response and attribution path. No other definition gains a claim, and general original-submitter response guards remain unchanged. MCP may submit, start and observe but may never claim, inspect response authority, APPLY or REJECT this setup review, including through its original submission capability.
2. An eligible claimant holds a current authenticated HUMAN session on an admitted person CLI, TUI or desktop frontend, with the existing native peer/person checks and current REVIEW/RESPOND access for the exact same active profile. API-key sessions, frontend strings, invocation origin, operation receipts and observed references are not proof. Eligibility is any such authorized human session, not just an attended MCP parent.
3. The original invocation admission and execution lease must remain live. Claim and response recheck runtime boot, exact profile/custody binding, authority generation, claimant connection/session, operation identity, interaction, revision, current checkpoint and reviewed proposal digest. The claim also checks the digest of the canonical review document displayed to the person against a fresh runtime resolution. Observation never issues or restores authority.
4. Under the existing authority fences and broker lock, an explicit claim assigns the retained process-local bearer to that exact human connection/session and current checkpoint. No bearer, transferable capability or secret crosses IPC. The runtime stores the claimant proof separately from the invocation binding; it must not relabel an MCP submission as human.
5. There is one claimant at a time. An identical claim by the current holder is idempotent only while every bound coordinate is current. Another human receives a typed already-claimed refusal. There is no stealing, reconnect recovery or reconstruction after loss. Claimant retirement, original invocation retirement, boot/generation change, or interaction/revision/proposal drift invalidates authority and requires a new setup run. An already consumed decision is never replayed as a second effect.
6. APPLY/REJECT use the existing exact single-use response service and checkpoint validation. The claim grants no cancellation, detach, resume, replay or execution ownership. Durable journal attribution records the verified claimant and human decision separately from MCP invocation provenance, with exact checkpoint coordinates and time; client-declared actor text is not attribution proof.
7. Reject settles NONE. Apply uses exactly the reviewed role `plan_digest`; plan drift refuses and asks for a new run. UNKNOWN is established before role apply, and an undeterminable apply outcome remains UNKNOWN. Desktop in-process provisioning before sign-in stays governed by its existing native path.

## Implementation

We will extend the existing response broker and verified native/person transport with this bounded claim. A dedicated versioned request/reply belongs in `src/cadrumo_client/contracts/operation_access.py`. Admission in `src/cadrumo_runtime/host/profile_connection_operations.py` verifies the person and authority coordinates before sending an attested worker message through `contracts/profile_worker.py`, `adapters/profile_worker_operation_client.py` and `host/worker_operation_requests.py`. `host/operation_host.py` adds the provisioning-specific path; `_projection_authority.py` owns atomic bearer reassignment. No general observe-to-respond shortcut is introduced.

Add explicit review/claim/answer actions to CLI and the existing TUI operation modal. Extend `session_hold_operations.py` for the canonical holder and `native/application/src/person_operations.rs:692` through `native/desktop/src-tauri/src/agent/person/native.rs:13` for the installed desktop's native person relay. Response inspection remains a separate capability check after claim. Exact wire names and private helper decomposition are implementation hypotheses; the constraints above are the commitment.

`2026-10-26-rust-component-provisioning-plan` carries the authorized implementation: S01 owns the claim contract, claimant attestation, broker transition, attribution and backend tests and lands first. S02 owns CLI review/claim/answer, S03 the TUI action, and S05 the desktop person relay and integrated cross-surface verification. All Steps remain open until their actual implementation and verification settle.

Required verification covers MCP original-submitter claim/inspect/APPLY/REJECT refusal; forged human label and API-key refusal; independent human same-profile success; wrong profile, boot, generation, drift and retired leases; concurrent human claims with one holder; replay and foreign actor; retirement fencing; and unchanged response guards for other operations. The runtime and surface integration checks must prove exact role digest application, NONE rejection, UNKNOWN after lost apply, and separate MCP/human journal attribution. These are required future checks, not claimed test results.

## Rationale

A makes the accepted human-only approval behavior usable for MCP-started operations while preserving existing broker custody, single-use semantics and runtime authority. It adds only the missing explicit issuance transition. A parent-only predicate is insufficient because the profile-key admission route has no necessary parent. B was rejected because it withdraws the accepted MCP-started setup behavior.

## Consequences

A adds a public protocol transition, a narrow broker reassignment method, explicit claimant lifetime and journal attribution. The runtime must fence two distinct live principals: the invocation owner and the human responder. Claim loss deliberately requires a new run instead of recovering authority from a journal or observed reference. Reconsider this restriction only through another explicit decision if recovery or wider operation handoff is needed.

The owner authorized these scoped reconciliations on 2026-10-27:

- In `2026-10-26-rust-component-provisioning-registered-operations-adr`, extend constraint 7: "For `config.provision.setup` only, a separately authenticated HUMAN session on the same exact active profile may explicitly claim the current REVIEW through the runtime while its original invocation lease remains live, under the exact bindings and retirement rules of the human-review-authority amendment. This grants only current REVIEW response authority and does not transfer the operation's admission or ownership." Extend constraint 8 and Implementation to require runtime refusal of all MCP response actions and the explicit human claim/answer actions on CLI, TUI and desktop.
- In `2026-08-11-tui-architecture-adr`, D4, append: "For `config.provision.setup` only, the runtime may explicitly assign the live current REVIEW bearer to a separately verified same-profile human under the provisioning human-review-authority ruling. This dedicated claim is a fresh guarded issuance transition; observation, reattachment and replay still confer no response authority, and all other operation response guards remain unchanged."
- Other accepted MCP parity and native provisioning rulings are reused unchanged. Option B is rejected; MCP retains setup submission and observation.

A with the same-profile HUMAN predicate is accepted. The registered-operations constraints and TUI D4 are refined within this explicit scope; implementation and its verification remain pending under the plan.
