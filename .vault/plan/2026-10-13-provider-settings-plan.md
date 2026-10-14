---
tags:
  - '#plan'
  - '#provider-settings'
date: '2026-10-13'
tier: L2
related:
  - '[[2026-10-13-provider-settings-adr]]'
  - '[[2026-10-11-mcp-parity-full-parity-adr]]'
  - '[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-13-provider-settings-reference]]'
modified: '2026-10-14'
body_schema: body-v2
body_hash: 'sha256:80e3860d998207dc57509a90e5884d9c2997cb6d1f1cffffcca0616ee4b9d7b6'
---

# `provider-settings` plan

Profile-owned provider settings, one shared resolver, and the hosted-agent hand-off on a standard-input frame.

## Description

Approved 2026-10-13.

Authorization basis, all first-hand from the owner on 2026-10-13:

- Approval of the design: "approved". `2026-10-13-provider-settings-adr` was first proposed for review by the other sessions, on the owner's instruction. Peer review continues, and its findings arrive as amendments to the accepted record.
- They approved the handed-over decision proposal and implementation outline: "Noted and agreed. Provde a handover promtp for the cadrumo design session to implement this work". This is recorded in the handover's `acceptance.md`, written at 09:27 +02:00.
- To this session, superseding the environment hand-off in that proposal: "do standard input frame".
- To this session: "whatever you're doing that is not a comprehe sive list of support api keys. there's a lot more cadrumo agent supports."
- To this session: "Development mode is essential. how aelse woudl e be , you developing?"
- To UI-DESIGN2, as quoted in `2026-10-13-desktop-agent-host-live-lane-adr`: "DO NOT ALLOW MY API KEYS TO BE EXPOSED".

The handover does not authorize commits: "Do not commit or push unless separately requested". This plan grants none. Commits, pushes, real-profile mutation and entering a real provider key each need a separate request.

Operator authorized executing P02.S07-S08 on 2026-10-14.

The plan is governed by `2026-10-13-provider-settings-adr`, which P01.S01 records together with its in-place amendments to `2026-10-11-mcp-parity-full-parity-adr`, `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr` and `2026-10-04-canonical-environment-adr`. Custody, session and profile-state authority stay with the August successor records.

Two records belong to another session and are not edited here: `2026-10-12-desktop-agent-host-adr` and `2026-10-13-desktop-agent-host-live-lane-adr`, both proposed. Both agree with the new ADR's standard-input rule; the live-lane record withdrew its environment hand-off. The cadrumo-agent repository is outside this assignment, so S02 and S03 stay open until that author acts.

Code locators come from `tui`, re-grounded in `2026-10-13-provider-settings-reference`.

## Steps

### Phase `P01` - Decisions

Records the provider-settings decision and its amendments in both vaults, and hands the agent-side work to its author.

- [x] `P01.S01` - Record and accept the provider-settings ADR with its evidence reference, and amend the full-parity, agent-inside and canonical-environment ADRs in place; `.vault/adr/2026-10-13-provider-settings-adr.md, .vault/reference/2026-10-13-provider-settings-reference.md, the three amended ADRs`.
- [x] `P01.S02` - Amend the cadrumo-agent records for per-profile scope, development-mode-only fallback and the standard-input frame, through the agent vault's own verbs; `agent .vault/adr/2026-10-10-cadrumo-integration-provider-settings-adr.md, agent .vault/adr/2026-10-11-cadrumo-integration-hosting-contract-adr.md`.
- [x] `P01.S03` - Hand the cadrumo-agent author a note for the standard-input frame reader and the worker credential pipe that replaces the environment copy; `agent api/app.py, agent control/worker_management.py`.

### Phase `P02` - Encrypted provider settings

Delivers the provider catalog and a per-profile encrypted settings record, managed only by the person, with masked status on every frontend.

- [x] `P02.S04` - Declare the provider catalog as Cadrumo data, listing the providers cadrumo-agent supports as sourced from cadrumo-agent, with credential kinds, base URLs and consumers, and add strict domain types for the record; `src/cadrumo/_data/registry/cadrumo/, src/cadrumo/domain/provider_settings/`.
- [x] `P02.S05` - Enroll the SECRET, PROFILE_LOCAL, PROCESS_LOCAL, LOCAL_ONLY namespace in inventory, deletion, reset and uninstall, excluded from portable export and restorative backup; `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py, namespace_registry.py`.
- [x] `P02.S06` - Build the repository and application service for status, set or replace, remove and reset, with revision guards and refusal of corrupt records; `src/cadrumo/adapters/persistence/provider_settings/, src/cadrumo/application/provider_settings/`.
- [x] `P02.S07` - Enroll set, remove and reset as person acts in ACCESS_ADMINISTRATION_OPERATIONS or an equivalent declared set, since remove and reset carry no secret, so the runtime refuses all three on MCP and generic execute at dispatch with PERSON_ACT_REQUIRED, with a test per action; `src/cadrumo/application/operations/person_acts.py, src/cadrumo/entrypoints/runtime/profile_connection_operations.py`.
- [x] `P02.S08` - Add the CLI commands with secrets on the protected standard-input channel and masked output; `src/cadrumo/entrypoints/cli/config/`.
- [x] `P02.S09` - Desktop contract: published aeat command names, JSON output shapes and typed refusal codes for provider-settings status, set/replace, remove and reset, documented for the desktop sessions in 2026-10-13-provider-settings-desktop-contract-reference. Status is one read listing every provider with id, display_name (brand name, every locale), auth_kind (api_key, api_key_with_base_url, oauth_token_or_provider_sign_in, provider_sign_in_only), consumers (extraction, assistant), mode (key, oauth_token, provider_sign_in, disabled, unset), available, source (profile, environment, none), readiness (ready, not_verified, missing, disabled, sign_in_required, unusable), an optional closed reason code, default_base_url (absent where the catalog has none), base_url only when stored, and revision as the guard every action sends. Every field is a closed enumeration. Remove persists disabled, reset returns to unset, and set stores without remote validation, so readiness is not_verified until first use. Refusals are not_signed_in, profile_locked, invalid_key_format, base_url_rejected, revision_conflict, committed_readback_failed, person_act_required (a frontend that may not change credentials asked) and unknown. Status is read on demand only, with no push and no polling; `src/cadrumo/entrypoints/cli/config/, docs/`.
- [ ] `P02.S10` - Add the TUI profile settings view for masked status and guarded set, replace, remove and reset; `src/cadrumo/entrypoints/tui/profile/`.

### Phase `P03` - Shared resolver

Delivers one resolver bound to the exact profile, login and settings generations, which extraction and every model client use.

- [ ] `P03.S11` - Build the resolver bound to the exact profile, login and settings generations, with automatic environment fallback for unset records in development storage mode only and no environment path in installed builds; `src/cadrumo/application/provider_settings/, src/cadrumo/core/storage_environment.py`.
- [ ] `P03.S12` - Held for the owner's ruling on Cadrumo's own document reading: provider settings serve the agent's lanes only, so extraction and LLMClient key handling stay unchanged until the owner decides; `src/cadrumo/application/ledger/invoice_draft_extraction.py, src/cadrumo/adapters/outbound/llm/client.py`.

### Phase `P04` - Hosted-agent controller

Delivers the app-owned controller that starts a contained cadrumo-agent tree and hands it credentials once on a bounded standard-input frame.

- [ ] `P04.S13` - Host the agent tree in the runtime's profile host, bound to the requesting session, in a kill-on-close job, and launch its cadrumo-mcp relay as the bundle's executable by absolute path with the pinned storage root, never a bare name, so a lane agent can never resolve the per-user default root; test that the relay's root is the pinned one; `src/cadrumo/application/agent_host/, src/cadrumo/adapters/local_runtime/, src/cadrumo/entrypoints/runtime/`.
- [ ] `P04.S14` - Write the credentials and the gateway bearer once on a bounded standard-input frame behind one seam, keep keys out of environment blocks, argv, files and the cadrumo-mcp relay, and guard the development lane: refuse agent_root_unmarked unless the root the runtime serves is a marked lane root (.cadrumo-agent-lane.json), and always refuse the per-user default root; `src/cadrumo/application/agent_host/`.
- [ ] `P04.S15` - Implement aeat app agent serve to the desktop-agent-host plan's Launcher protocol: argv --agent-source, stdin {"bearer"} held open with EOF as stop, stdout agent_ready, agent_refused with its seven codes and agent_stopped, ephemeral loopback ports; publish only for the current generation and restart from committed values on a credential change; `src/cadrumo/entrypoints/cli/, src/cadrumo/application/agent_host/`.

### Phase `P05` - Lifecycle barrier

Delivers the canonical cross-process barrier that stops profile work at promotion, logout, lock and expiry before another profile is published.

- [ ] `P05.S16` - Reorder sign-in so that, after candidate B's authentication succeeds and before B is admitted or its receipt minted, every other profile's human sessions are retired and their agent trees stopped; a failed B keeps A; today _sign_out_other_profiles runs only after _finish_login admitted B and minted its receipt (profile_connection_sessions.py:113,196); `src/cadrumo/entrypoints/runtime/profile_connection_sessions.py, src/cadrumo/application/user_profile/`.
- [ ] `P05.S17` - Observe the session without touching idle time, so background polling never extends a sign-in; `src/cadrumo/application/user_profile/, src/cadrumo/application/agent_host/`.

### Phase `P06` - MCP contract and live proof

Aligns cadrumo-agent's relay with the tui MCP surface and proves the whole path on real disposable profiles.

- [ ] `P06.S18` - Align cadrumo-agent relay expectations with the cadrumo-mcp full surface tool list, coordinated with agent relay S05 and testbed S02; `src/cadrumo_harness/mcp/main.py, src/cadrumo/application/operations/mcp_surfaces.py`.
- [ ] `P06.S19` - Prove on real disposable profiles a provider turn, tool work, profile switch, logout, expiry, credential rotation and MCP refusal of credential management; `src/cadrumo/application/agent_host/tests/, src/cadrumo_harness/mcp/tests/`.
- [ ] `P06.S20` - Coordinate the cross-session desktop work, not built by this session: the Tauri host commands and the webview, including the profile settings section and agent panel status, owned by the desktop design sessions UI-DESIGN1 and UI-DESIGN2; `native/desktop/src-tauri/src/shell/, native/desktop/frontend/src/`.
- [x] `P06.S21` - Coordinate cadrumo-agent's side, owned by BUILD2: a bounded standard-input frame reader before any store or provider opens, keyed by agent_credential_id and carrying the gateway bearer; the worker's keys and internal token over its own stdin pipe instead of os.environ.copy; ephemeral gateway and worker ports reported in the ready line; ready and refused lines on stdout under hosting contract 1; and a hosted start that mounts the Cadrumo relay; `agent api/app.py, agent control/worker_management.py, agent worker/app.py, agent providers/provider_readiness.py`.
- [ ] `P06.S22` - Coordinate the bundle, owned by BUILD1: regenerate the agent locks (native/agent/<target>.txt) against the CADRUMO_AGENT_SOURCE_DIR folder's revision that carries the frame reader and worker pipe, and add a bundle.agent smoke check of hosting contract 1, before any installed-build proof in S19; `native/agent/, dev/packaging/`.
- [ ] `P06.S23` - Coordinate the desktop agent lane, owned by UI-DESIGN2: the lane harness stores the developer's key into its throwaway profile with aeat config provider set --secrets-stdin before a run, and reads aeat config provider status instead of its stored-key placeholder; `dev/desktop_agent_live/lane.py`.

## Parallelization

P01 runs first. Its S02 and S03 belong to cadrumo-agent's author and do not block P02. P02 then P03, in order. After P03, P04 and P05 may run in parallel with disjoint write ownership:

- P04 owns the hosted-agent controller and its frame-writer seam.
- P05 owns the runtime lifecycle barrier and the session observation.
- They share only the generation types P03 publishes.

P06 runs last. It needs S02 and S03 landed in cadrumo-agent.

P06.S20 is the desktop sessions' work. UI-DESIGN1 and UI-DESIGN2 own the Tauri host commands and the webview, and build against the contract published by P02.S09. This session does not build it.

Execution uses a model-split team, on the owner's instruction:

- Haiku agents do discovery, tool calls and test-run summaries.
- Sonnet agents do easy mechanical edits only, never architecture-level coding.
- Opus agents at medium effort do the real coding, and may use Haiku helpers.

## Verification

- Every check runs on real disposable encrypted profiles, built through the product's own profile creation and sign-in. No mock of the component under test.
- Cover:
  - ciphertext at rest;
  - refusal when logged out, expired, retired or after a same-profile re-login;
  - A/B isolation and revision conflicts;
  - `disabled` versus `unset`, with automatic environment fallback in development storage mode and none in an installed build;
  - the shared resolution behind extraction and the assistant;
  - masked status leaking neither a secret nor a fingerprint;
  - refusal of the person's credential acts on MCP and through generic `execute`, at dispatch;
  - credential rotation, failed and successful profile switches (including a switch from an external CLI), and startup racing logout;
  - host death and reaping of descendants;
  - no key in any environment block, argv, file, log or tool child.
- Gates, all clean before a Step closes: `just check-code check-format check-types check-import-boundaries check-secure-store-write-paths check-persistence-write-paths`, then the integration and interactive OS-keychain lanes where their subjects apply.
- P06 needs a real provider turn and useful authenticated MCP work. A handshake or a constructed component is not capability proof. A missing prerequisite is reported as a failure, never simulated.
- Report each command and its exact result.
