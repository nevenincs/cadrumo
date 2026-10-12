---
tags:
  - '#plan'
  - '#desktop-agent-host'
date: '2026-10-12'
tier: L2
related:
  - '[[2026-10-12-desktop-agent-host-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]'
  - '[[2026-06-10-llm-evidence-classification-adr]]'
  - '[[2026-06-10-ledger-evidence-enforcement-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
  - '[[2026-10-10-mcp-parity-parity-mechanism-adr]]'
  - '[[2026-10-03-application-packaging-adr]]'
modified: '2026-10-12'
body_schema: body-v2
body_hash: 'sha256:e0e402a9fb70e23dc2050755babfd72d2bc2b3948eba6c8248b997fa96d4749b'
---

# `desktop-agent-host` plan

Host cadrumo-agent from the desktop through a Cadrumo launcher, with agent state encrypted in the profile's storage boundary, documents in Cadrumo custody and explicit consent before a provider receives private content.

## Description

Draft. Not approved. This plan waits for acceptance of `2026-10-12-desktop-agent-host-adr`, which is `proposed`. No Step executes on that record's authority until it is accepted. Each amendment Step (`P02.S11`, `P02.S12`, `P03.S18`, `P03.S19`) also needs the owner's own authorization of its text. Evidence: `2026-10-12-desktop-agent-host-reference`.

### Binding basis

The owner's five first-hand rulings of 2026-10-12, as the ADR's Problem Statement records them:

- Protection at rest: private profile data, conversations and attachments stay under Cadrumo's encrypted-storage requirement. There is no plaintext exchange folder.
- Explicit consent: private content goes to an external model provider only after explicit consent naming the provider and the content. Signing in, attaching a file or approving an operation never implies it. Passwords and authentication secrets stay outside the agent and provider boundary.
- Bundled shipping: a compatible cadrumo-agent ships inside Cadrumo's package through the normal build and release. Compatibility is declared. Absence or incompatibility fails clearly. Nothing is downloaded or installed at runtime.
- Tauri technical session ownership: the Tauri technical session implements the Rust host from a contract given to it. There is no competing Rust workstream. Phase `P05` is that contract's work list; it assigns nothing to anyone.
- Profile-scoped location: agent state lives within the selected profile's storage boundary, respects the explicit storage-root override, and is resolved and supplied by Cadrumo. There is no global agent root. The agent cannot choose another profile's location. A profile-local folder alone is not encryption.

Two rulings committed today in `ba94b05d5f` also bind this plan:

- `2026-10-10-mcp-parity-plan` `P02.S18` is closed: a message the person sends to the assistant counts as the person's activity, and the assistant's own calls never do (`2026-10-04-application-sign-in-adr`, Lifetime). Under it, the person's messages in the agent column extend the sign-in's idle deadline; the assistant's own work does not.
- The MCP surface loses the `session`, `installation`, `authenticate` and `authorization_*` tools (`2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`). cadrumo-agent's relay, which demands those tools today, must drop them; that is cadrumo-agent work.

Three further first-hand owner rulings of 2026-10-12, relayed by the coordinator, bind Phase `P04`:

- Latest Anthropic versions only: "ensure we're working against the latest anthropic versions, no backwards or old version support." The `anthropic` SDK floor is the latest release, `anthropic>=1.13.0,<2`, in both `pyproject.toml` entries (the `anthropic` extra and the dev list), with no 0.x compatibility path. Only current Claude models are used; old model ids are not kept.
- Model names are derived, never hardcoded. `anthropic` is a real optional dependency of Cadrumo (the `anthropic` extra, the default LLM provider). All Anthropic code is updated, and model names come from the Anthropic Models API list, which reports id, display name, creation time, input and output token limits and capabilities, and carries no pricing and no tier or family field. Model roles are capability requirements checked against that list.
- No PyPI for cadrumo-agent: "we will not publish cadrumo agent to pypi, ever. we do not have a settled method of provisioning the repo." Bundling waits for open decision 5.

The SDK upgrade itself was done as separate direct work outside this plan, and is not a Step. Commits `9f56dd5962` and `3b5bb1d8ee` pin `anthropic>=1.13.0,<2`, and remove `temperature`, which 1.x dropped from `messages.create`, from the Anthropic adapter (`src/cadrumo/adapters/outbound/llm/providers/anthropic.py`). It is declared unsupported through the adapter's unsupported-parameters capability, with no `extra_body` fallback. The commits also update `src/cadrumo/adapters/outbound/llm/tests/test_parameter_capability_boundary.py`, including a loopback wire test. `src/cadrumo/adapters/outbound/llm/role_fitness.py` stays unchanged, because its probe only ever calls the httpx-based local adapter. `P04.S28` builds on that work.

Contract 7 of the ADR says cadrumo-agent is "a locked dependency in Cadrumo's lock file, installed by the normal provisioning". The no-PyPI ruling means the ADR needs that wording revised before acceptance, to name the method decision 5 settles.

### Decision coverage

- `2026-10-12-desktop-agent-host-adr` (proposed) governs every Phase.
- `2026-10-04-application-sign-in-adr` governs `P03.S18` and `P03.S23` to `P03.S26` (resume exception, key door, launcher admission).
- `2026-10-04-desktop-shell-adr` governs `P03.S19` and Phase `P05` (long-lived child, host commands, no runtime connection in the shell).
- `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr` governs `P02.S12`, `P02.S14`, `P03.S23` and `P06.S44` (person acts refused on MCP, no secret in the agent's path).
- `2026-06-10-llm-evidence-classification-adr` governs `P01.S07` and Phase `P02` (consent, no temp files, no agent file-path route).
- `2026-06-10-ledger-evidence-enforcement-adr` governs `P01.S01` to `P01.S06` (encrypted evidence bytes, no plaintext financial documents outside custody).
- `2026-09-26-mcp-purpose-authentication-adr` governs `P01.S07` and `P02.S17` (bytes never enter MCP results; only registered projections).
- `2026-10-10-mcp-parity-parity-mechanism-adr` governs `P01.S04` to `P01.S10` and `P02.S14` (new capability is a registered operation answered alike on every frontend).
- `2026-10-03-application-packaging-adr` (proposed) governs `P04.S29` and `P04.S30` (the release manifest binds the Python packages).
- `P04.S28` rests on the owner's Anthropic rulings below and on open decision 6. No ADR in this vault governs model selection; if decision 6 settles a persisted selection or pricing contract, it is recorded in its own ADR before `P04.S28` executes.

The ADR's affected cadrumo-agent records (conversation-data-posture, profile-data-root, shipping-and-versioning, project-boundary, hosting-contract) are amended in that repository, not here.

### Open choices and the Steps they block

The ADR's Consequences name four choices for the owner. Each blocks the Steps listed until it is settled.

1. Agent state shape: encrypted sibling root with a released key (proposed) or agent state as Cadrumo secure objects with no key release. Blocks `P03.S20`, `P03.S21`, `P03.S22`, `P03.S24`, `P03.S25`, `P03.S26`, and downstream `P06.S39` to `P06.S42`. If secure objects are chosen, `P03.S20` to `P03.S22` are replaced and `P03.S24` releases no key.
2. Launcher identity: a new `agent-host` frontend (proposed) or the CLI frontend with a narrow door. Blocks the text of `P03.S18`, and `P03.S23`, `P03.S24`, `P03.S25`, `P03.S26`. `P02.S14` refuses consent acts on MCP now; refusal on `agent-host` lands with `P03.S23`.
3. Cadrumo-side consent granularity: per profile, provider and model (enforceable now) or per conversation, which needs cadrumo-agent to carry the conversation id on its tool connection. Blocks only the per-conversation matching in `P02.S17` and the matching assertions of `P06.S43`. The grant record of `P02.S13` names the conversation either way.
4. Implementation owner for the Tauri host: no running session claims `native/desktop/src-tauri`. Blocks all of Phase `P05` (`P05.S31` to `P05.S37`) and the desktop parts of `P06.S39`, `P06.S43` and `P06.S46`.

Two further owner decisions are open since the ADR was written:

5. cadrumo-agent provisioning: how the cadrumo-agent repository is provisioned into Cadrumo's build, given it is never published to PyPI. Today the wheel selector accepts only single PyPI registry wheels (`dev/packaging/runtime_wheel_selection.py:193-243`), and path sources are excluded from the constraint export (`dev/packaging/uv_constraints.py:62-66`) and from the product-cohort check (`dev/packaging/native/product.py:101-105`). Blocks `P04.S29`, the Bundled path of `P04.S30`, the installed-distribution comparison of `P04.S27`, and every Step that needs a packaged agent: `P03.S25`, `P03.S26` and Phase `P06`.
6. Model selection policy: which model serves each role when several in the live list meet its capability requirement, and what replaces the price table now keyed by model id, since the Models API carries no prices. Blocks `P04.S28`.

Phases `P01` and `P02` (except the per-conversation part of `P02.S17`), the declarations and refusals of `P04.S27`, and the NotBundled path of `P04.S30` are blocked by no choice.

### Cross-project dependency

cadrumo-agent owns contract 4 of the ADR and its own packaging. That covers: one SQLCipher connector for every store opener, keyed from the standard-input frame; no log files, token files or IPC secret files in hosted mode; `tmp` and `scratch` emptied after every run; hosted lanes limited to the direct Anthropic lane; documents read through Cadrumo projections; a hosting-contract version bump and a store-format version; a `__main__` module; a relay tool list without the removed MCP tools; an `anthropic` range that admits `>=1.13.0,<2`; and superseding records for its five affected decisions. These were handed over to cadrumo-agent on 2026-10-12 and are not Steps here. cadrumo-agent is never published to PyPI; `P04.S29` waits for open decision 5.

Hosted use with real data waits for two proofs: cadrumo-agent's recorded tool-access proof for the `cadrumo` tool server, and `2026-10-10-mcp-parity-plan` `P10.S70` (live proof of MCP inside the signed-in profile). Until both exist, the agent column shows the agent as unavailable. `P06.S44` produces Cadrumo's side of that evidence.

### Scope and hypotheses

Out of scope: the Claude Code lane (excluded until a run proves nothing persists in plaintext), Node bundling, and any change in the cadrumo-agent repository.

Hypotheses within the ADR, free to change in execution: operation ids `documents.add`, `documents.list`, `documents.remove`, `documents.role`, `documents.text` and the consent ids; CLI leaves under `aeat app documents` and `aeat app consent`; new packages `src/cadrumo/application/documents/`, `src/cadrumo/application/consent/`, `src/cadrumo/application/agent_host/`, `src/cadrumo/domain/consent/` and `native/desktop/src-tauri/src/shell/agent/`; the lane `dev/runtime_lifecycle/desktop_agent_host.py` modelled on `dev/runtime_lifecycle/live_sign_in.py`. The ADR names the launcher `aeat agent serve`, but the CLI rule keeps the root families `config` and `app`; `P03.S25` settles the leaf placement before it lands.

## Steps

### Phase `P01` - documents in custody

Deliver conversation-linked documents in Cadrumo custody, reachable through registered operations on every frontend, independent of the open choices.

- [ ] `P01.S01` - Add a typed conversation link and an agent attachment source to the attachment manifest under a new manifest schema version, keep readers of the previous version working, rewrite no stored manifest, and prove both versions round trip through the real AttachmentStore; `src/cadrumo/domain/attachments/models.py, src/cadrumo/domain/attachments/enums.py, src/cadrumo/adapters/persistence/storage/attachment.py, src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py, src/cadrumo/adapters/persistence/storage/tests/`.
- [ ] `P01.S02` - Add per-attachment unlink and delete to the attachment store, deleting encrypted bytes only when no transaction, invoice or conversation link remains and no legal hold covers them, with typed refusals and real-store tests; `src/cadrumo/adapters/persistence/storage/attachment.py, src/cadrumo/domain/attachments/service.py, src/cadrumo/application/evidence/profile_legal_hold.py, src/cadrumo/adapters/persistence/storage/tests/`.
- [ ] `P01.S03` - Create the document intake module: a media-type allow-list (pdf, xml, the image types ledger evidence accepts, csv, tsv, xlsx, xls, ofx, qfx, docx, txt, md, zip), a per-file size bound, in-memory ZIP expansion under member-count, expanded-size, nesting-depth and link bounds with each member admitted on its own, a typed refusal reason per file, and no plaintext temp file; test with synthetic fixtures including a ZIP bomb; `src/cadrumo/application/documents/intake.py, src/cadrumo/application/documents/tests/`.
- [ ] `P01.S04` - Register the documents.add operation: read each named path once in the worker, apply intake, store accepted files in custody with their conversation link and role, return per-file digests and refusal reasons, record its MCP surface facts, and add its executor conformance scenario; `src/cadrumo/application/documents/add_operation.py, src/cadrumo/entrypoints/operation_composition.py, src/cadrumo/application/operations/mcp_surface_facts.py, src/cadrumo/application/documents/tests/`.
- [ ] `P01.S05` - Register the documents.list (by conversation), documents.remove and documents.role operations over the custody store, removing only links and leaving held or still-referenced bytes, each with MCP surface facts and an executor conformance scenario; `src/cadrumo/application/documents/list_operation.py, src/cadrumo/application/documents/remove_operation.py, src/cadrumo/application/documents/role_operation.py, src/cadrumo/entrypoints/operation_composition.py, src/cadrumo/application/operations/mcp_surface_facts.py`.
- [ ] `P01.S06` - Let a custody document with the ledger role enter the existing evidence and import review flow by attachment id, without a second copy of its bytes outside custody, and prove it reaches human review rather than canonical records; `src/cadrumo/application/documents/ledger_routing.py, src/cadrumo/application/ledger/evidence_add_operation.py, src/cadrumo/application/ledger/import_operation.py`.
- [ ] `P01.S07` - Register the documents.text read operation that serves a bounded text projection per document from in-memory decryption through existing readers, never bytes or a path, with transcription digest and length, a typed unsupported answer for types without a local reader, and refusal of every request until the consent check of P02.S17 admits it; `src/cadrumo/application/documents/text_projection_operation.py, src/cadrumo/adapters/inbound/pdf/, src/cadrumo/application/operations/mcp_surface_facts.py`.
- [ ] `P01.S08` - Add the aeat app documents add, list, remove, role and text leaves as declarative command fragments over the registered operations, with typed text and JSON envelopes and locale keys authored through dev.locales; `src/cadrumo/entrypoints/cli/_app_documents_command_specs.py, src/cadrumo/entrypoints/cli/runtime_documents.py, src/cadrumo/entrypoints/cli/command_operation_table.py, src/cadrumo/entrypoints/cli/command_graph.py`.
- [ ] `P01.S09` - Add the TUI documents surface that submits the same registered operations and shows per-file refusals, loading and unavailable states distinctly from empty; `src/cadrumo/entrypoints/tui/runtime_documents.py, src/cadrumo/entrypoints/tui/documents/`.
- [ ] `P01.S10` - Extend the cross-frontend parity, surface-fact census and MCP surface pin tests to the documents operations and prove CLI, TUI and MCP answers agree through the real registry and access policy; `src/cadrumo/entrypoints/tests/test_operation_frontend_parity.py, src/cadrumo/entrypoints/tests/test_operation_surface_facts.py, src/cadrumo/application/operations/tests/test_mcp_surface_pins.py`.

### Phase `P02` - consent

Deliver explicit, person-granted consent naming provider, model and content, refused on MCP, recorded for every served projection, with Cadrumo-side enforcement at the granularity choice 3 settles.

- [ ] `P02.S11` - Draft the amendment text for 2026-06-10-llm-evidence-classification-adr admitting person-granted consent for hosted-assistant projections beside per-invocation digest-bound consent, and present it for owner authorization; P02.S13 to P02.S17 do not execute before it is accepted; `.vault/adr/2026-06-10-llm-evidence-classification-adr.md`.
- [ ] `P02.S12` - Draft the amendment text for 2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr naming consent grant and withdraw as person acts and agent data key delivery as a door outside MCP, and present it for owner authorization; `.vault/adr/2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr.md`.
- [ ] `P02.S13` - Add the consent grant record and its secure-object namespace: profile, conversation, provider, model and content scope (person messages, document digests, Cadrumo tool results), active and withdrawn states, and revision-guarded writes with real-store tests; `src/cadrumo/domain/consent/grant.py, src/cadrumo/adapters/persistence/llm/consent_grants.py, src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`.
- [ ] `P02.S14` - Register consent grant, withdraw and list operations as person acts refused on the MCP frontend through the existing person-act policy, with MCP surface facts and executor conformance scenarios; `src/cadrumo/application/consent/grant_operations.py, src/cadrumo/application/operations/person_acts.py, src/cadrumo/entrypoints/operation_composition.py, src/cadrumo/application/operations/mcp_surface_facts.py`.
- [ ] `P02.S15` - Add the CLI consent leaves and the TUI consent surface over the grant operations, naming provider, model and each item, with Allow as a deliberate action; `src/cadrumo/entrypoints/cli/_app_consent_command_specs.py, src/cadrumo/entrypoints/cli/command_operation_table.py, src/cadrumo/entrypoints/tui/runtime_consent.py`.
- [ ] `P02.S16` - Record every served document projection and private tool result in the consent ledger with digest, provider, model and frontend under a new ledger record version; `src/cadrumo/adapters/persistence/llm/consent_ledger.py, src/cadrumo/application/documents/text_projection_operation.py`.
- [ ] `P02.S17` - Add the hosted-assistant surface check that refuses document projections and private tool results without an active grant matching profile, provider and model, and leave per-conversation matching unavailable until choice 3 is settled; `src/cadrumo/application/operations/mcp_surfaces.py, src/cadrumo_harness/mcp/admitted_operations.py, src/cadrumo/application/documents/text_projection_operation.py`.

### Phase `P03` - agent root, key and launcher

Deliver the profile-scoped agent root, the per-profile agent data key, the agent-host key door and the aeat agent serve launcher, once choices 1 and 2 are settled and the sign-in and shell amendments are authorized.

- [ ] `P03.S18` - Draft the amendment text for 2026-10-04-application-sign-in-adr granting the agent-host frontend its resume exception and its key door, and present it for owner authorization; P03.S22 to P03.S26 do not execute before it is accepted; `.vault/adr/2026-10-04-application-sign-in-adr.md`.
- [ ] `P03.S19` - Draft the amendment text for 2026-10-04-desktop-shell-adr admitting a long-lived aeat agent serve child and the closed list of agent host commands with a Tauri channel stream, and present it for owner authorization; P05 does not execute before it is accepted; `.vault/adr/2026-10-04-desktop-shell-adr.md`.
- [ ] `P03.S20` - Add the storage taxonomy category and scope for the per-profile agent root under the storage root, derived from the resolved root and the bound profile, honouring CADRUMO_LOCAL_STORAGE_ROOT, excluded from reclaim, with tests for both root forms; `src/cadrumo/core/storage_taxonomy.py, src/cadrumo/core/storage_taxonomy_locations.py, src/cadrumo/core/storage_environment.py, src/cadrumo/application/storage_management/service.py`.
- [ ] `P03.S21` - Add the agent-root deletion journal state and owner receipt to profile deletion, modelled on the session-acceleration step, so profile deletion and all-profile reset remove the root with receipts and refuse on change since preflight; `src/cadrumo/application/user_profile/custody_transactions.py, src/cadrumo/application/user_profile/custody_service.py, src/cadrumo/application/user_profile/login_session.py, src/cadrumo/application/config_reset.py`.
- [ ] `P03.S22` - Add the per-profile agent data key namespace (SECRET, profile-local, process-local, finite lifetime) and its mint-on-first-use reader, modelled on the review-package signing key, with real-store tests; `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py, src/cadrumo/adapters/persistence/profile/agent_data_key.py, src/cadrumo/core/classification/policies.py`.
- [ ] `P03.S23` - Add the agent-host frontend identity: admitted by resuming the stored sign-in, refused every person act including consent grants, and covered by the cross-frontend parity tests; `src/cadrumo/application/operations/registry.py, src/cadrumo/application/operations/person_acts.py, src/cadrumo/application/user_profile/operation_access_policy.py, src/cadrumo/entrypoints/runtime/profile_connection_admission.py, src/cadrumo/entrypoints/tests/test_operation_frontend_parity.py`.
- [ ] `P03.S24` - Add the agent-host runtime door that releases the agent data key and the provider credential in secret frames only to an admitted agent-host connection for its bound profile, never through a registered operation result; `src/cadrumo/entrypoints/runtime/agent_host_door.py, src/cadrumo/adapters/local_runtime/frontend_client.py, src/cadrumo/entrypoints/runtime/enrollment_connections.py`.
- [ ] `P03.S25` - Add the aeat agent serve launcher start path: read the bearer frame from standard input, admit on agent-host by resume, verify the bundled agent against the manifest and supported range, resolve and create the agent root, fetch key and credential from the door, start the agent with its standard-input frame, wipe copies, and print one agent_ready line or one typed refusal; `src/cadrumo/entrypoints/cli/agent_serve.py, src/cadrumo/application/agent_host/launcher.py, src/cadrumo/entrypoints/cli/command_graph.py, src/cadrumo/entrypoints/cli/command_operation_table.py`.
- [ ] `P03.S26` - Add launcher supervision: on session retirement re-resume once and stop the agent if refused; on standard-input close cancel the live run, shut the agent down, end and confirm the process tree within a bounded deadline; test with real processes; `src/cadrumo/application/agent_host/supervision.py, src/cadrumo/entrypoints/cli/agent_serve.py, src/cadrumo/adapters/local_runtime/frontend_client.py`.

### Phase `P04` - packaging and compatibility

Bundle a compatible cadrumo-agent inside the package by the provisioning method open decision 5 settles, with a manifest agent statement, a declared supported range and typed absent or incompatible refusals, and derive every Claude model from the Anthropic Models API; the anthropic SDK upgrade runs as separate direct work outside this plan.

- [ ] `P04.S27` - Declare the supported cadrumo-agent version range, hosting-contract and store-format versions, the comparison with the manifest and with cadrumo-agent version JSON, and the typed agent_service_absent and agent_service_incompatible refusals in the error catalogue; the installed-distribution comparison follows the provisioning method of open decision 5; `src/cadrumo/application/agent_host/compatibility.py, src/cadrumo/core/errors/error_codes.py`.
- [ ] `P04.S28` - Remove every hardcoded Claude model id: derive models from the Anthropic Models API list (id, display name, creation time, token limits, capabilities), express each model role as a capability requirement such as image input for vision, replace the id-keyed price table and the name-prefix tiering, and drop the hardcoded config defaults; the selection policy and the price-table replacement wait for open decision 6; `src/cadrumo/core/model_catalogue.py, src/cadrumo/adapters/outbound/llm/client.py, src/cadrumo/adapters/outbound/llm/pricing.py, src/cadrumo/domain/transactions/model_tier.py, src/cadrumo/core/config_llm_fields.py, src/cadrumo/core/config_runtime_fields.py, src/cadrumo/core/tests/test_model_catalogue.py`.
- [ ] `P04.S29` - Bundle cadrumo-agent into the build by the provisioning method open decision 5 settles, never from PyPI, adapting as that method requires the wheel selector, the constraint export and the product-cohort check, which today accept only single registry wheels and exclude path sources; declare the launcher entry it needs, and assert that no Node runtime or adapter enters the bundle; `dev/packaging/runtime_wheel_selection.py, dev/packaging/uv_constraints.py, dev/packaging/native/product.py, dev/packaging/native/layout.py, pyproject.toml, uv.lock`.
- [ ] `P04.S30` - Add the manifest agent statement (bundled, distribution version, hosting-contract version, store-format version) mirroring the user-docs statement, mapped to Bundled, NotBundled or Undeclared in the native package reader and the desktop environment; the Bundled path follows open decision 5 and P04.S29; `dev/packaging/native/assemble.py, native/application/src/package.rs, native/desktop/src-tauri/src/environment.rs`.

### Phase `P05` - desktop host

Deliver the Tauri host side of contract 1 and wire the agent column to real host commands, once choice 4 names the owner of native/desktop/src-tauri.

- [ ] `P05.S31` - Add the shell agent lifecycle: start the digest-verified aeat agent serve child with a projected environment only while signed in and the runtime is available, write the minted bearer frame, read the ready or refusal line, and stop by closing standard input on every contract 1 trigger with a bounded process-tree end; `native/desktop/src-tauri/src/shell/agent/lifecycle.rs, native/desktop/src-tauri/src/shell/mod.rs, native/application/src/child.rs`.
- [ ] `P05.S32` - Add the closed list of token-checked agent host commands mapped one-to-one to gateway routes, and the Tauri channel for the run stream, keeping the bearer in the Rust host and the CSP unchanged; `native/desktop/src-tauri/src/shell/agent/commands.rs, native/desktop/src-tauri/src/shell/agent/stream.rs, native/desktop/src-tauri/src/shell/token.rs`.
- [ ] `P05.S33` - Add agent_pick_files: open the native file dialog in the Rust host and return opaque handles with display name, size and media type, keeping paths in the host; `native/desktop/src-tauri/src/shell/agent/files.rs`.
- [ ] `P05.S34` - Add the Cadrumo-operation host commands for documents add from opaque handles, list, remove and role, and consent grant, withdraw and list, each spawning a fixed digest-verified aeat child; `native/desktop/src-tauri/src/shell/agent/cadrumo_commands.rs`.
- [ ] `P05.S35` - Serve AgentViews from the Tauri host through the host commands, with loading and refusal distinct from empty and every unbuilt view unavailable; `native/desktop/frontend/src/shell/host.ts, native/desktop/frontend/src/shell/agentViews.ts`.
- [ ] `P05.S36` - Drive the agent lifecycle stop triggers from the sign-in observation and pushed events that mcp-parity P10.S68 delivers, coordinated with that Step's owner; `native/desktop/src-tauri/src/shell/sign_in/observation.rs, native/desktop/src-tauri/src/shell/agent/lifecycle.rs`.
- [ ] `P05.S37` - Wire Composer, AttachmentWell and ConsentPrompt in the agent column to the real host commands, asking for consent before the first send, on a provider or model change and before a newly referenced document is shared; `native/desktop/frontend/src/components/agent/Composer.tsx, native/desktop/frontend/src/components/agent/AttachmentWell.tsx, native/desktop/frontend/src/components/agent/ConsentPrompt.tsx, native/desktop/frontend/src/components/AgentColumn.tsx`.

### Phase `P06` - end-to-end verification

Prove each of the nine ADR verification criteria on the packaged build with a synthetic encrypted profile, without mocks of the component under test.

- [ ] `P06.S38` - Create the desktop agent host lane and its justfile recipe, and prove criterion 1 (package): the manifest agent statement matches the installed distribution, and removing it or changing its version yields agent_service_absent or agent_service_incompatible with nothing downloaded; `dev/runtime_lifecycle/desktop_agent_host.py, dev/runtime_lifecycle/tests/, justfile`.
- [ ] `P06.S39` - Prove criterion 2 (lifecycle): launcher and agent start only while signed in and stop on sign-out, lock, idle and absolute expiry, runtime restart, profile switch and window close, leaving no process, and the shell holds no connection, key or credential; `dev/runtime_lifecycle/desktop_agent_host.py, native/desktop/tests/packaged/`.
- [ ] `P06.S40` - Prove criterion 3 (location): with and without CADRUMO_LOCAL_STORAGE_ROOT agent state appears only under the bound profile agent root, a second profile root is never touched, and deletion and reset remove it with receipts; `dev/runtime_lifecycle/desktop_agent_host.py`.
- [ ] `P06.S41` - Prove criterion 4 (at rest): after a real conversation with a document, a byte scan of the storage root, OS temp and user cache directories finds no known message, tool-result or document string outside encrypted stores, and the stores do not open without the key; `dev/runtime_lifecycle/desktop_agent_host.py`.
- [ ] `P06.S42` - Prove criterion 5 (secrets): the agent data key, provider credential, gateway bearer and Cadrumo password appear in no environment block, command line, file, log or transcript; `dev/runtime_lifecycle/desktop_agent_host.py`.
- [ ] `P06.S43` - Prove criterion 6 (consent): a send without a grant is refused, the prompt names provider, model and items, withdrawal stops sends and projections, grants cannot be created from MCP or agent-host, and each served projection is in the consent ledger; `dev/runtime_lifecycle/desktop_agent_host.py, native/desktop/tests/packaged/`.
- [ ] `P06.S44` - Prove criterion 7 (tool path): a real signed-in Cadrumo read through the hosted assistant succeeds and is refused after sign-out, with no sign-in, sign-out, lock, attendance or secret-carrying tool reachable, as evidence for cadrumo-agent tool-access proof paired with mcp-parity P10.S70; `dev/runtime_lifecycle/desktop_agent_host.py`.
- [ ] `P06.S45` - Prove criterion 8 (documents): each accepted type, a ZIP and a ZIP bomb fixture, custody digests, conversation links, refusals with reasons, ledger-data documents reaching review, and deletion with holds; `dev/runtime_lifecycle/desktop_agent_host.py, src/cadrumo/application/documents/tests/`.
- [ ] `P06.S46` - Prove criterion 9 (interface): the packaged agent column shows every unbuilt or refused capability as unavailable with its reason; `native/desktop/frontend/tests/agent.spec.ts, native/desktop/tests/packaged/`.

## Parallelization

Run now, once the ADR is accepted:

- Phase `P01` and Phase `P02` run concurrently. `P01` owns `src/cadrumo/domain/attachments/`, `src/cadrumo/adapters/persistence/storage/attachment.py`, `src/cadrumo/application/documents/` and the documents CLI and TUI modules. `P02` owns `src/cadrumo/domain/consent/`, `src/cadrumo/application/consent/`, `src/cadrumo/adapters/persistence/llm/` and the consent CLI and TUI modules.
- The declarations and refusals of `P04.S27` run beside `P01` and `P02`.
- `P04.S28` runs once open decision 6 is settled and the separate SDK upgrade has landed. It owns `src/cadrumo/core/model_catalogue.py`, `src/cadrumo/adapters/outbound/llm/client.py`, `src/cadrumo/adapters/outbound/llm/pricing.py`, `src/cadrumo/domain/transactions/model_tier.py`, `src/cadrumo/core/config_llm_fields.py` and `src/cadrumo/core/config_runtime_fields.py`, and may run beside every other Phase.

Shared files take one writer at a time, each commit serialized: `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py` (`P01.S01`, `P02.S13`, `P03.S22`), `src/cadrumo/entrypoints/operation_composition.py`, `src/cadrumo/application/operations/mcp_surface_facts.py`, `src/cadrumo/entrypoints/cli/command_operation_table.py`, `src/cadrumo/application/operations/person_acts.py`, `pyproject.toml` and `uv.lock` (`P04.S29` and the separate SDK upgrade).

Hard ordering:

- `P02.S11` is accepted before `P02.S13` to `P02.S17` execute.
- `P01.S07` lands before `P02.S16` and `P02.S17`, which edit its module; `P02.S17` is what opens `P01.S07` to requests.
- Phase `P03` starts after choices 1 and 2 are settled. `P03.S18` is accepted before `P03.S22` to `P03.S26`. Inside the Phase: `P03.S20` before `P03.S21`; `P03.S22` and `P03.S23` before `P03.S24`; `P03.S24` and `P04.S27` before `P03.S25`; `P03.S25` before `P03.S26`.
- `P04.S29` starts when open decision 5 settles how the cadrumo-agent repository is provisioned. `P04.S30` can land its NotBundled path first and its Bundled path after `P04.S29`. `P03.S25`, `P03.S26` and Phase `P06` need a packaged agent, so they follow `P04.S29`.
- Phase `P05` starts after choice 4 names the owner of `native/desktop/src-tauri` and `P03.S19` is accepted. `P05.S31` needs `P03.S25` for a real child. `P05.S35` and `P05.S37` may proceed against an unavailable host once `P05.S32` fixes the command names. `P05.S36` follows `2026-10-10-mcp-parity-plan` `P10.S68`.
- Phase `P06` runs on a packaged build that contains `P01` to `P05`. `P06.S38` needs `P04`. The pytest part of `P06.S45` can run after `P01`.

## Verification

Plan-wide checks, each with its final exit status read and the intended tests confirmed in the summary:

- `just check-import-boundaries`, `just check-style`, `just check-format` and `just check-types` pass, with no scope weakened.
- `just test-unit`, `just test-cli`, `just test-tui` and `just test-integration` pass, and their summaries include the new documents, consent, storage, key and launcher tests.
- `src/cadrumo/entrypoints/tests/test_operation_frontend_parity.py`, `src/cadrumo/entrypoints/tests/test_operation_surface_facts.py` and `src/cadrumo/application/operations/tests/test_mcp_surface_pins.py` pass with every new operation in the production registry.
- `just check-locales` passes for every new key in every supported locale.
- `uv run --no-sync pytest dev/quality/tests/test_no_git_cli.py` passes.
- For Phase `P04`: `just test-packaging-preflight` and `just test-native-bundle` pass, and the built manifest carries the agent statement.
- For `P04.S28`: `rg -n "claude-[a-z0-9.-]+" src/cadrumo --glob "!**/tests/**"` finds no model id in product code, and `src/cadrumo/core/tests/test_model_catalogue.py` proves each role resolves by capability against a Models API list.
- For Phase `P05`: `just test-native-host` passes, and `npm run check` and `npm test` in `native/desktop/frontend` pass.
- `just verify-desktop-agent-host PACKAGE` (created by `P06.S38`) passes each of the nine ADR criteria on the packaged build with a synthetic encrypted profile.

Review: a formal review at each Phase close and an integrated review at plan close. Hosted use with real data is not claimed until cadrumo-agent's recorded tool-access proof and `2026-10-10-mcp-parity-plan` `P10.S70` both exist. The plan is complete when every Step is closed and the final review passes.
