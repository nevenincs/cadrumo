---
tags:
  - '#plan'
  - '#agent-owned-models'
date: '2026-10-25'
tier: L2
related:
  - '[[2026-10-25-agent-owned-models-adr]]'
  - '[[2026-10-24-rust-component-provisioning-adr]]'
  - '[[2026-10-18-dependency-provisioning-unified-setup-adr]]'
  - '[[2026-10-19-provider-settings-tax-model-runs-adr]]'
  - '[[2026-10-13-provider-settings-adr]]'
  - '[[2026-06-13-llm-evidence-classification-adr]]'
  - '[[2026-10-13-application-distribution-native-bundle-llm-extra-adr]]'
  - '[[2026-10-13-agent-attachments-adr]]'
modified: '2026-10-25'
body_schema: body-v2
body_hash: 'sha256:fd1a65b6afa84d976cc43d43c43406ed9c8f20975889c7103f97c9ed546feb6e'
---

# `agent-owned-models` plan

## Description

Approved 2026-10-25

Authorization basis: the owner's first-hand rulings in conversation on 2026-10-25, recorded in `2026-10-25-agent-owned-models-adr`. They are R1 (no model definitions in Cadrumo; cadrumo-agent's provider catalogue is the sole source of providers and models), R2 (Ollama program pins and supervision stay; the person's selected model is pulled, integrity by Ollama's manifest), R3 (one dispatch path through the agent; the direct local adapter is deleted; consent by a typed `reads_off_host` flag), R4 (licence shown, person decides), R5 (per-role selection, `NO_SELECTION` refusal, no fallback, vision-capable only for the vision role) and R6 (cadrumo-agent gains an `ollama` provider and a new catalogue schema).

The plan removes every AI model definition from Cadrumo and routes all tax model calls through the agent service, with the person choosing a lane and model per role. Evidence is `2026-10-24-rust-component-provisioning-reference`. Decision coverage is the new `2026-10-25-agent-owned-models-adr`, which amends `2026-10-24-rust-component-provisioning-adr`, `2026-10-18-dependency-provisioning-unified-setup-adr`, `2026-10-19-provider-settings-tax-model-runs-adr`, `2026-10-13-provider-settings-adr`, `2026-06-13-llm-evidence-classification-adr`, `2026-10-13-application-distribution-native-bundle-llm-extra-adr` and `2026-10-13-agent-attachments-adr`. It also notes the proposed `2026-08-07-unstructured-document-ingestion-provisioning-adr`, which the new ADR links and which is not an authority for any Step. The accepted ADRs are linked in `related`.

Scope by phase:

- P01 prepares what needs no new catalogue: the selection store and wire (provider-settings ADR; tax-model-runs ADR constraint 5), the role-based lookup, removal of unread hosted ids and the model-definition gate (new ADR constraint 1).
- P02 consumes the new catalogue and decides consent from the flag (new ADR constraints 4, 6, 7). It is blocked on cadrumo-agent.
- P03 makes the agent the only dispatch path and deletes the Cadrumo model tables, pins, settings and ranking (new ADR constraints 1, 3, 8; tax-model-runs ADR amendment).
- P04 removes model pins from the Rust engine and feeds it the selection (new ADR constraints 2, 9, 10; Rust provisioning and unified-setup amendments).
- P05 delivers the selection surfaces, documentation, locales and the conformance review (new ADR constraints 5, 6).

Open point for the executor: the selection is stored by the agent service, whose administration is served over the desktop person channel and is absent from `aeat` (provider-settings ADR constraint 5). `P05.S25` adds the CLI and TUI set operations through the tax operation surface and the runtime-to-service frame. Before that Step, confirm with the owner that setting a role's model, which holds no secret, may use that surface.

## Steps

### Phase `P01` - Independent prep

Land the per-role selection store and wire, role-based lookup, removal of the unread hosted ids and the model-definition gate. None of it needs cadrumo-agent's new catalogue.

- [ ] `P01.S01` - Add the per-profile, per-role model selection record and store with guarded revisions; absent means none and corrupt refuses; `src/cadrumo_agent_service/providers/domain/record.py, src/cadrumo_agent_service/providers/persistence/store.py, src/cadrumo_agent_service/providers/application/ports.py, src/cadrumo_agent_service/providers/persistence/tests`.
- [ ] `P01.S02` - Select by role in ModelRunService.lookup and refuse NO_SELECTION when the role has none, with no fallback to another lane or a default selection; `src/cadrumo_agent_service/providers/application/model_runs.py, src/cadrumo_agent_service/providers/application/tests`.
- [ ] `P01.S03` - Serve the selection on the authenticated service API and the typed wire contracts: read all roles, set and clear one role; `src/cadrumo_agent_service/admin.py, src/cadrumo_agent_service/contracts.py, src/cadrumo_agent_service/providers/application/service.py`.
- [ ] `P01.S04` - Return the per-role selection state through the runtime-to-service lookup frame so the tax side and the CLI and TUI can read it; `src/cadrumo/application/operations/model_runs.py, src/cadrumo_runtime/host/profile_connection_model_runs.py, src/cadrumo_agent_service/host/model_run_relay.py`.
- [ ] `P01.S05` - Read the selection in the desktop host and expose it to the webview as a typed snapshot; `native/desktop/src-tauri/src/agent/admin.rs, native/desktop/src-tauri/src/agent/gateway.rs`.
- [ ] `P01.S06` - Delete the hosted model ids and their re-exports, which have no production reader; `src/cadrumo/domain/transactions/model_tier.py, src/cadrumo/domain/transactions/__init__.py, src/cadrumo/domain/transactions/llm.py`.
- [ ] `P01.S07` - Add the model-definition gate: refuse model-name and digest literals and model tables in shipped sources, with an explicit burn-down list of current files that later Steps empty, isolated fixtures proving it detects each defect, and a stated stopping point; `dev/quality/tests/test_no_model_definitions.py`.

### Phase `P02` - Consume the new catalogue

Parse cadrumo-agent's new catalogue schema version with its typed fields and decide consent from reads_off_host. Blocked until cadrumo-agent delivers the schema and its ollama provider.

- [ ] `P02.S08` - Parse the new schema version with the typed fields vision, installed, size_bytes, context_length, licence and reads_off_host, the recommended set and the run options; refuse an entry without reads_off_host; `src/cadrumo_agent_service/providers/domain/catalog.py, src/cadrumo_agent_service/providers/domain/tests`.
- [ ] `P02.S09` - Admit the keyless loopback auth kind and a loopback base URL, and project them into the credential schema and resolution; `src/cadrumo_agent_service/providers/domain/record.py, src/cadrumo_agent_service/providers/application/resolution.py, src/cadrumo_agent_service/adapters/agent_provider_catalog.py, src/cadrumo_agent_service/adapters/provider_catalog_metadata.py`.
- [ ] `P02.S10` - Validate a role selection against the catalogue: the model must exist and the vision role requires a vision-capable entry; carry licence, size_bytes and reads_off_host in the lane lookup reply; `src/cadrumo_agent_service/providers/application/service.py, src/cadrumo_agent_service/providers/application/model_runs.py, src/cadrumo_agent_service/providers/application/contracts.py`.
- [ ] `P02.S11` - Decide off-host consent from the lane's reads_off_host flag in the tax adapter and bind the token to the resolved lane; `src/cadrumo/adapters/outbound/llm/consent.py, src/cadrumo/adapters/outbound/llm/providers/agent.py, src/cadrumo/adapters/outbound/llm/preconditions.py`.

### Phase `P03` - One dispatch path

Send every tax model call through the agent service and delete Cadrumo's direct Ollama adapter, model tables, pins, model settings, ranking and pin recipe.

- [ ] `P03.S12` - Route text extraction, classification and statement reading through the agent adapter; `src/cadrumo/adapters/outbound/llm/text_classifier.py, src/cadrumo/adapters/outbound/llm/statement_reading.py, src/cadrumo/adapters/outbound/llm/evidence_draft_text.py`.
- [ ] `P03.S13` - Route vision transcription and image classification through the agent adapter; PDF rasterisation stays on the Cadrumo side; `src/cadrumo/adapters/outbound/llm/vision_classifier.py, src/cadrumo/adapters/outbound/llm/evidence_draft_vision.py, src/cadrumo/application/ledger/invoice_draft_extraction.py`.
- [ ] `P03.S14` - Route column-role mapping and the supply-nature proposal through the agent adapter and remove the configured-default-provider route; `src/cadrumo/adapters/outbound/llm/column_role_mapping.py, src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py, src/cadrumo/entrypoints/ledger_evidence_extraction_composition.py`.
- [ ] `P03.S15` - Delete LocalAdapter, the LLMProvider.LOCAL member, the local branches of dispatch, consent and pricing, role fitness and their tests; make admission read size_bytes from the catalogue entry; `src/cadrumo/adapters/outbound/llm/providers/local.py, src/cadrumo/adapters/outbound/llm/client.py, src/cadrumo/adapters/outbound/llm/role_fitness.py, src/cadrumo/adapters/outbound/llm/pricing.py, src/cadrumo/core/config_support.py, src/cadrumo/core/provenance_stamp.py, src/cadrumo/application/ledger/invoice_evidence_extract_operation.py, src/cadrumo/adapters/outbound/llm/tests`.
- [ ] `P03.S16` - Delete the model catalogue tables, the model part of the pin loader, the pin data file and the select_model_for_role ranking, keeping ModelRole in a module that holds only roles; `src/cadrumo/core/model_catalogue.py, src/cadrumo/core/local_ai_pins.py, src/cadrumo/_data/dependencies/local_ai_models.toml, src/cadrumo/application/provisioning.py, src/cadrumo/application/local_reader.py`.
- [ ] `P03.S17` - Delete the four local-model settings and their defaults, move num_ctx to the catalogue run option, and remove their lines from the environment templates; `src/cadrumo/core/config_runtime_fields.py, env/.env.example`.
- [ ] `P03.S18` - Delete the pin-local-ai recipe, its generator and the pinned model names in the dev lanes; shrink the gate burn-down list; `justfile, dev/env/local_ai_model_pins.py, dev/runtime_lifecycle/mcp_proof_support.py, dev/quality/tests/test_no_model_definitions.py`.

### Phase `P04` - Rust engine

Drop model pins from the engine, take the selected local models as input, pull them with integrity by Ollama's manifest, and keep Ollama program pins and supervision unchanged.

- [ ] `P04.S19` - Remove model pins, model items and licence data from the engine and the staged pin data; keep program pins; `native/application/src/provisioning/pins.rs, native/application/src/provisioning/items.rs, native/application/src/provisioning/local_ai/models.rs`.
- [ ] `P04.S20` - Accept the selected local models as role, model-name and size_bytes triples in the plan and setup commands and bind them in the plan digest; `native/application/src/provisioning/protocol.rs, native/application/src/provisioning/plan.rs, native/application/src/provisioning/role_host.rs`.
- [ ] `P04.S21` - Pull each selected model on the supervised server, report rows from the selection and Ollama's installed list, and drop digest-based stale; compute the hardware floor from the supplied size_bytes; `native/application/src/provisioning/local_ai/models.rs, native/application/src/provisioning/local_ai/hardware.rs, native/application/src/provisioning/state.rs, native/application/src/provisioning/engine.rs`.
- [ ] `P04.S22` - Pass the stored selection from the Python component client and the desktop setup host to the role, and delete the pinned model fixtures; `src/cadrumo/adapters/outbound/components/client.py, src/cadrumo/adapters/outbound/components/protocol.py, native/desktop/src-tauri/src/shell/setup/components.rs, native/desktop/frontend/src/dev/setupFixture.ts`.
- [ ] `P04.S23` - Prove the pull path with a synthetic model id against the fake Ollama server and remove the remaining model literals from engine tests; `native/application/src/provisioning/local_ai/fake_ollama.rs, native/application/src/provisioning/local_ai/models`.

### Phase `P05` - Surfaces and docs

Give the person a per-role selection on every surface with licence and vision capability, update documentation and the four locales, prove surface conformance and review.

- [ ] `P05.S24` - Add the per-role selection control to the desktop agent settings, showing licence, vision capability and the recommended entry; `native/desktop/frontend/src/components/agent/AgentSettingsPopover.tsx, native/desktop/frontend/src/dev/catalogue`.
- [ ] `P05.S25` - Add the selection read and set to the TUI setup flow and the CLI through registered operations, and the read to MCP; `src/cadrumo/entrypoints/tui/setup/screen.py, src/cadrumo/entrypoints/cli/config/_provision_command_specs.py`.
- [ ] `P05.S26` - Update the how-to, CLI reference, technical articles and API pages that describe local models, pins or the direct adapter; `docs/how-to/classify-with-llm.md, docs/cli/config/provision.rst, docs/technical/articles/027-local-reader-provisioning-workstation-health-and-application-contracts.md, docs/technical/articles/168-profile-custody-provisioning-and-runtime-configuration.md`.
- [ ] `P05.S27` - Add and translate the selection, licence and NO_SELECTION strings in en, es, ca and hu in the informal singular through the dev.locales set-batch workflow; `src/cadrumo/locales/en, src/cadrumo/locales/es, src/cadrumo/locales/ca, src/cadrumo/locales/hu`.
- [ ] `P05.S28` - Prove selection conformance across desktop, TUI, CLI and MCP and empty the gate burn-down list; `dev/quality/tests/test_no_model_definitions.py, src/cadrumo/entrypoints/tui/setup/tests`.

## Parallelization

Phase P01 may run in parallel, with disjoint ownership.

- `P01.S01` owns the selection record and store under `src/cadrumo_agent_service/providers/domain` and `persistence`. `P01.S02`, `P01.S03` and `P01.S04` follow it, because they read the port it defines.
- `P01.S02` owns `model_runs.py`. `P01.S03` owns `admin.py`, `contracts.py` and `providers/application/service.py`. `P01.S04` owns the tax-side and runtime relay files. These three run in parallel once `P01.S01` lands.
- `P01.S05` owns `native/desktop/src-tauri/src/agent` and follows `P01.S03`'s wire contract.
- `P01.S06` owns `src/cadrumo/domain/transactions` and is independent of every other Step. `P01.S07` owns `dev/quality/tests/test_no_model_definitions.py` and is independent; later Steps edit only its burn-down list, one Step at a time.

Phase P02 is serial and blocked until cadrumo-agent delivers its catalogue schema version and `ollama` provider. `P02.S08` lands first. `P02.S09` and `P02.S10` follow and own disjoint files. `P02.S11` follows `P02.S10`.

Phase P03 starts after P02. `P03.S12`, `P03.S13` and `P03.S14` own disjoint consumer files and run in parallel. `P03.S15` follows all three, because it deletes the adapter they stop using. `P03.S16` follows `P03.S15`, `P03.S17` follows `P03.S16`, and `P03.S18` is last. They share the burn-down list in the gate, so they serialize.

Phase P04 owns `native/application` for `P04.S19` to `P04.S21` and `P04.S23`, which may run in parallel with P03 once P02 fixes the `size_bytes` field, because Rust and Python files are disjoint. They serialize with each other as `S19`, `S20`, `S21`, `S23`. `P04.S22` spans both languages and runs after P03 and `P04.S21`.

Phase P05 starts after P03 and P04. `P05.S24` (desktop), `P05.S25` (TUI and CLI) and `P05.S26` (documentation) own disjoint files and run in parallel. `P05.S27` follows the first two, because they fix the strings. `P05.S28` is last.

## Verification

The plan is complete when every Step is closed and these checks pass.

- `uv run --no-sync pytest dev/quality/tests/test_no_model_definitions.py` passes with an empty burn-down list, and its isolated fixtures show it fails on a model-name literal, a digest literal and a model table.
- A search of `src`, `native` and `dev` for the former default model ids, the pinned manifest digests and `local_ai_models.toml` finds nothing outside synthetic test ids.
- `just check-import-boundaries`, `just check-style`, `just check-format` and `just check-types` pass, and `cargo test` in `native/application` and `native/desktop/src-tauri` passes.
- The agent-service tests for the selection store and `ModelRunService.lookup` show: a stored selection is returned per role; a role with no selection refuses `NO_SELECTION`; no other lane is used; a vision role naming a non-vision entry is refused.
- A tax model call for each role (vision transcription, text extraction, column-role mapping, supply-nature proposal) reaches the agent adapter in a test over the real client, and no code path imports a direct Ollama adapter.
- A catalogue entry with `reads_off_host` true needs the digest-bound consent token; an entry with it false needs none; an entry without the field is refused.
- The engine plans and pulls a synthetic model named by the selection against the fake Ollama server, the plan digest changes when a name or size changes, and no engine state depends on a pinned model digest.
- `dev.locales` coverage shows the new keys in `en`, `es`, `ca` and `hu`, and the CLI renders the `NO_SELECTION` refusal in each.
- A selection made on the desktop is read back unchanged by the CLI, TUI and MCP lookup, and the licence and vision capability are shown on each selection surface.
- `vaultspec-core vault check all` and `vaultspec-core vault plan check` pass, and the final cohesive review passes.

Phase P02 and the Steps that need its output (`P03.S12` to `P03.S15`, `P04.S22`, `P05.S24` to `P05.S28`) are verified only after cadrumo-agent delivers the new catalogue schema and its `ollama` provider. Until then they stay open and no check above is claimed for them.
