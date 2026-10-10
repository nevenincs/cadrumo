---
tags:
  - '#reference'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:3e32fde04a7ddc322a7508cba584829bc98df56fa722c8d45ca55288261503c9'
related: []
---

# `mcp-parity` reference: `approval step`

This record collects the code and record facts that bear on a step in which the person approves a sensitive act an agent asks for. Every code locator is relative to the root of this repository, on branch `feature/tui`, read on 2026-10-10 by static analysis with nothing executed; the tree held other sessions' uncommitted work. Records named `2026-10-10-cadrumo-integration-...` belong to the vault of the cadrumo-agent repository and are cited by name. It states facts only and recommends nothing.

## Summary

- A review's answer belongs to the session that submitted the operation, and the MCP `respond` tool answers from that session, so as built an agent would answer its own review (section 1).
- Access evaluation has an unused policy field that refuses for want of transaction authority, and an approval binding already exists for automation enrollment (section 2).
- The runtime knows a peer's owner and process id and holds a handle to it. It knows no ancestry, and the frontend is whatever the client declared at login (section 3).
- The command line marks commands destructive or hand-off and dispatch reads neither flag (section 4).
- The desktop shell holds no runtime connection, and accepted records place approval prompts in the terminal interface while naming this decision as open (section 5).
- The cadrumo-agent records fix the behaviour of a reserved command in the assistant's terminal: it runs nothing, returns at once, and runs when issued again after approval (section 6).

## 1. The review interaction and its response capability

- The operation host keeps each fresh submission in memory, keyed by operation id with the submitting session (`src/cadrumo/entrypoints/runtime/operation_host.py:108`, `:300-301`).
- A submission that resolves to an earlier operation is not stored and its binding is discarded, so a replay gets no response capability (`src/cadrumo/entrypoints/runtime/operation_host.py:300-305`).
- An apply, reject or inspect response is refused with `RESPONSE_AUTHORITY_REQUIRED` unless the actor reference names the calling session, that session submitted the operation, and a capability is held (`src/cadrumo/entrypoints/runtime/operation_host.py:525-532`, `:540-543`).
- The MCP `respond` tool builds apply and reject from the caller's own session, so the session that submitted an operation is the one that answers its review (`src/cadrumo_harness/mcp/admitted_operations.py:210-245`).
- A pending interaction is a checkpoint that binds interaction id, operation identity, revision, kind, a continuation digest, an optional expiry, the digest of a single-use response token, a reviewed-proposal digest and optional baseline and proposed-effect digests (`src/cadrumo/application/operations/interactions.py:29-41`, `:112-121`).
- Consuming a response checks identity, revision, continuation, proposal, token, expiry and, for apply, baseline and proposed effect (`src/cadrumo/application/operations/interactions.py:152-214`).
- Interaction kinds are a closed set of input, choice, review, apply and reject; the public projection offers only none, review available, or unsupported for input and choice (`src/cadrumo/core/operations.py:153-160`; `src/cadrumo/application/operations/frontend_projection.py:35-38`, `:117-128`).
- A pending interaction is valid only in lifecycle `waiting_for_interaction`, and a terminal projection cannot carry one (`src/cadrumo/application/operations/frontend_projection.py:219-243`).
- Lifecycle includes `settling` and `terminal`; effect is one of none, updated, partial, unknown (`src/cadrumo/core/operations.py:8-18`, `:79-85`).
- Start requires the submitting session, but resume requires only custody for the calling session and a fresh RESUME guard (`src/cadrumo/entrypoints/runtime/operation_host.py:315-317`, `:409-429`).
- The terminal interface's operation modal shows a review projection as serialized JSON (`src/cadrumo/entrypoints/tui/operations/modal.py:271-284`).
- The MCP `execute` tool reports any runtime refusal at submission as outcome `unresolved` with a code (`src/cadrumo_harness/mcp/admitted_operations.py:109-118`).

## 2. Access evaluation

- The human gate compares session kind only, and the declared frontend list is checked on the next line (`src/cadrumo/application/user_profile/operation_access_policy.py:175-178`).
- The access policy has a field `transaction_authority_required` that refuses with `TRANSACTION_AUTHORITY_REQUIRED`, and every production resolver found sets it false (`src/cadrumo/application/user_profile/access_contracts.py:392`, `:431`; `src/cadrumo/application/user_profile/operation_access_policy.py:231-232`; `src/cadrumo/application/operations/access_resolution.py:251`; `src/cadrumo/application/ledger/llm_review_operation.py:107`).
- The access request carries profile, definition, action, frontend, periods and destination, and no field for the caller's origin (`src/cadrumo/application/user_profile/access_contracts.py:349-365`).
- Admission provenance records a fingerprint of the request payload with the approved scope and the authority generation (`src/cadrumo/entrypoints/runtime/operation_authority.py:234-241`; `src/cadrumo/application/operations/provenance.py:16-30`).
- An approval binding already exists for automation enrollment, naming worker, boot, profile binding, connection, session, operation, request and a review digest (`src/cadrumo/application/runtime/approval_binding.py:13-24`; `src/cadrumo/entrypoints/runtime/operation_authority.py:119-145`).
- The worker asks the runtime parent to authorize each action over a kernel-verified channel, sending connection, session, operation, access request and policy (`src/cadrumo/application/runtime/worker_authorization.py:38-48`; `src/cadrumo/adapters/local_runtime/worker_authorization.py:133-153`).
- The access-management door admits only the command-line and terminal-interface frontends with an active, unlocked OS login of the peer's owner (`src/cadrumo/entrypoints/runtime/profile_connection_access.py:65-72`).

## 3. What the runtime knows about a peer

- On Windows the runtime takes the pipe client's process id from the kernel, retains a process handle, requires its own owner SID and a live process, and reads the image path (`src/cadrumo/adapters/local_runtime/windows_channel.py:47-69`).
- Peer evidence is an owner id and a process id, with no ancestry or containment field, and the connection context adds only connection id and boot id (`src/cadrumo/application/runtime/contracts.py:159-165`; `src/cadrumo/application/runtime/transport.py:12-18`).
- On Linux the peer comes from `SO_PEERCRED` with a peer pidfd available, and on macOS from the audit token (`src/cadrumo/adapters/local_runtime/posix_channel.py:25-27`, `:44-52`, `:68-83`).
- A Job Object membership test exists, and its only use read is against the runtime's own worker job; that scope's comment says processes created by external brokers are outside its guarantee (`src/cadrumo/adapters/local_runtime/windows_process.py:189-195`, `:390-408`).
- The frontend is a field of the login request, stored on the connection, and a connection cannot change it (`src/cadrumo/entrypoints/runtime/profile_connection_admission.py:132-145`, `:156-168`; `src/cadrumo/entrypoints/runtime/profile_host.py:96-103`).
- A search of `native/**/*.rs` for Job Object calls matched only `native/manager/src/windows_lifecycle.rs`. A search for an assistant, relay or gateway host under `native/desktop/src-tauri/src`, `src/cadrumo` and `src/cadrumo_harness` found no such component.

## 4. Command-line policy

- Every command's execution policy has booleans `destructive`, `handoff` and `live_write`, projected into the operator-surface policy metadata (`src/cadrumo/entrypoints/cli/command_spec.py:66-70`; `src/cadrumo/application/operator_surface/command_ports.py:198-208`).
- Dispatch reads `live_write` and refuses it unconditionally; the dispatch lines read do not consult `destructive` or `handoff` (`src/cadrumo/entrypoints/cli/_command_runtime.py:331-346`, `:360`).
- `app modelo reconcile import` carries the hand-off policy (`src/cadrumo/entrypoints/cli/_modelo_nonwork_reconcile_command_specs.py:141`, `:177`; `src/cadrumo/entrypoints/cli/_modelo_nonwork_command_spec_policies.py:74-80`).
- `ledger.export` and `modelo.quickfile` set `requires_human`, which a session from the shared sign-in passes on any frontend the definition lists (`src/cadrumo/application/ledger/export_operation.py:241`; `src/cadrumo/application/modelo/quickfile_operation.py:399`).
- The sign-in exemption matches by verb-path prefix, and the command line resumes the stored sign-in only when a terminal can prompt (`src/cadrumo/entrypoints/cli/_bootstrap_exempt.py:357-386`; `src/cadrumo/entrypoints/cli/runtime_profile_admission.py:125-132`).

## 5. Desktop shell and accepted records

- The shell's sign-in observer runs the command-line status leaf and "never resumes a receipt or owns a runtime" (`native/desktop/src-tauri/src/shell/sign_in/observation.rs:1-2`; `native/desktop/src-tauri/src/shell/sign_in/mod.rs:43-56`, `:121-127`). These files hold another session's uncommitted work.
- Accepted records place approval prompts in the terminal interface and name this decision as open: "Approval prompts belong to the TUI" and "How MCP-originated approval requests are surfaced when no TUI is open" (`.vault/adr/2026-10-04-runtime-manager-architecture-adr.md:109`, `:314`, `:321`; `.vault/adr/2026-10-04-desktop-shell-adr.md:82`, `:93`).
- The accepted operation record says "Approval is a specialized interaction" and that observation "from a fresh process cannot recreate response authority" (`.vault/adr/2026-08-11-tui-architecture-adr.md:481-485`, `:505-511`).
- The accepted MCP record says "a lost transaction-specific human approval is not recreated from a root API key" (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:141`).

## 6. What the cadrumo-agent records require of Cadrumo

- `2026-10-10-cadrumo-integration-owner-rulings-research` records the owner's answers "Assistant, after asking each time", "Yes, approve in Cadrumo (Recommended)" and "Add a Cadrumo runtime check (Recommended)". The last option read: the runtime "refuses reserved operations to anything running inside the assistant's process tree unless the person approved".
- `2026-10-10-cadrumo-integration-terminal-access-adr` requires that a reserved command "runs nothing, returns at once saying the command awaits the person", and runs only when "the assistant issues the identical command again". It adds that "an approval is used once and lapses if not used", that the pending request is held "in memory only", and that "No command blocks waiting for a person".
- The same record requires "the host's Job Object given an identity its command line and runtime can check" and a published reserved set.
- `2026-10-10-cadrumo-integration-write-gate-adr` states that cadrumo-agent "makes no decision per call" and "never runs a turn again by itself". It notes that a preview-then-apply step is a human step "only if the host withholds the tool that answers it".
- `2026-10-10-cadrumo-integration-sign-in-deadline-adr` requires that an approval settle "within one sign-in" and that a reserved command still waiting when the sign-in ends "is dropped".

## Not verified

- Which Cadrumo process hosts the assistant, and whether it creates a Job Object. No code exists for either.
- Whether the runtime can open another process's Job Object and test a peer against it. Nothing in the code does this for a client peer.
- Any containment a client peer could be tested against on Linux or macOS.
- Whether the emitted command-surface manifest carries `destructive` and `handoff`. The metadata type was read; the emitter was not.
- The full list of commands flagged destructive or hand-off, which operations each submits, and whether any command submits more than one reserved operation.
- Where the supervisor resolves a caller's replay key relative to the SUBMIT guard. The supervisor's submission code was not opened.
- Whether the runtime parent or the profile worker can keep a private request in memory after the requesting connection closes. Worker lifetime rules were not read.
- How a command-line child started by the desktop host, with no console, would resume the sign-in. Only the refusal path was read.
- The terminal interface's existing automation-approval screens, the nearest analogue for a pending-approvals view.
- The cadrumo-agent facts about the host's Job Object and the agent's clocks, which were read in that repository's records and not in its code.
