---
tags:
  - '#adr'
  - '#agent-owned-models'
date: '2026-10-25'
modified: '2026-10-25'
body_schema: 'body-v2'
body_hash: 'sha256:cb6ccb06c559a12e995d2e6fce4962d7825b43e4c3e2d79fa5ca2b1f135225d8'
related:
  - "[[2026-10-24-rust-component-provisioning-reference]]"
  - "[[2026-10-24-rust-component-provisioning-adr]]"
  - "[[2026-10-18-dependency-provisioning-unified-setup-adr]]"
  - "[[2026-10-19-provider-settings-tax-model-runs-adr]]"
  - "[[2026-10-13-provider-settings-adr]]"
  - "[[2026-06-13-llm-evidence-classification-adr]]"
  - "[[2026-08-07-unstructured-document-ingestion-provisioning-adr]]"
  - "[[2026-10-13-application-distribution-native-bundle-llm-extra-adr]]"
  - "[[2026-10-13-agent-attachments-adr]]"
---
# `agent-owned-models` adr: `Agent-owned AI models` | (**status:** `accepted`)

## Problem Statement

Cadrumo defines AI models in four places, and cadrumo-agent already owns the same question.

- Pins: `src/cadrumo/_data/dependencies/local_ai_models.toml`, read by `src/cadrumo/core/local_ai_pins.py`, name each local model with a manifest digest, size and licence.
- A second table: `src/cadrumo/core/model_catalogue.py:80-588` lists candidate models per role with rankings, licences, memory figures and a hardcoded hosted Claude id. `src/cadrumo/application/provisioning.py:748-879` ranks them and `src/cadrumo/application/local_reader.py:344-410` resolves a role to one.
- Settings: four model-name fields with defaults (`src/cadrumo/core/config_runtime_fields.py:54-183`), and hosted ids with no production reader (`src/cadrumo/domain/transactions/model_tier.py:108-159`).
- Rust: `native/application/src/provisioning/pins.rs:292-392`, `items.rs:50-126` and `local_ai/models.rs:86-216` carry the same pins, and the desktop fixtures repeat them (`native/desktop/frontend/src/dev/setupFixture.ts:116-122`). The dev lanes `dev/runtime_lifecycle/mcp_proof_support.py:34-35` and `dev/env/local_ai_model_pins.py`, with the `pin-local-ai` recipe in `justfile`, maintain them.

Tax model calls also split in two. Local reads go straight to Ollama through `LocalAdapter` (`src/cadrumo/adapters/outbound/llm/providers/local.py`, dispatched in `src/cadrumo/adapters/outbound/llm/client.py:459-1083`). Hosted reads go through the agent service (`providers/agent.py`), where `ModelRunService.lookup` discards the role and picks the first catalogue entry with a default model (`src/cadrumo_agent_service/providers/application/model_runs.py:58-110`). The person can therefore not choose a model per role on either path (`2026-10-24-rust-component-provisioning-reference`, AI backend findings).

The owner ruled on 2026-10-25, first-hand in conversation: "don't hardcode model names when we have a proper cadrumo-agent", and "Ensure the provider is configured via the cadrumo-agent". Cadrumo is to stop defining models. Accepted rulings that say otherwise have to change before code can move.

## Considerations

- Providers and models are already cadrumo-agent's capability. Cadrumo keeps no provider list (`2026-10-13-provider-settings-adr` constraint 3 as amended 2026-10-14), and Claude model ids come from the Models API. Local models are the one place Cadrumo still keeps its own list.
- The catalogue parser accepts schema 3, an https-only base URL and three auth kinds (`src/cadrumo_agent_service/providers/domain/catalog.py:42-232`). A loopback Ollama needs a keyless auth kind and a loopback address, which that parser refuses today.
- Local reading through Ollama is a legitimate feature. The program is a component, not a model, so its archive pins stay (`2026-10-24-rust-component-provisioning-adr` constraint 7 and its 2026-10-24 amendment).
- Off-host consent is digest-bound per call (`2026-10-19-provider-settings-tax-model-runs-adr` constraint 8). Today "on-host" means "uses `LocalAdapter`". Once local reads go through the agent, on-host has to be a fact the catalogue states, not an inference from the path.
- Ollama verifies a pulled model against its content-addressed manifest, so Cadrumo needs no model digest of its own for integrity.
- The settings store for provider choices is per profile and sits in the agent service (`2026-10-13-provider-settings-adr` constraints 1 and 2). Per-role selection belongs beside it.
- cadrumo-agent is gaining an `ollama` provider and a new catalogue schema version. The brief was sent to that session on 2026-10-25. Cadrumo work that depends on its shape waits for delivery.

## Considered options

- **cadrumo-agent's catalogue is the sole source of providers and models, local included; one dispatch path through the agent; per-role selection by the person.** Chosen.
- **Keep the local lane as a separate path with Cadrumo's own model table, and send only hosted work through the agent.** Rejected: two sources of truth, two dispatch paths, and consent decided by path.
- **Keep a short Cadrumo default list for local roles, with the agent only for hosted.** Rejected by the owner: any Cadrumo-side name, size or ranking is a hardcoded model definition.
- **Drop local reading.** Rejected by the owner: on-host reading is a feature.
- **Pin model digests in Cadrumo for integrity.** Rejected: Ollama's manifest check covers integrity, and a pin freezes a catalogue Cadrumo does not own.
- **Gate local models on a Cadrumo commercial-use licence rule.** Rejected by the owner: the person decides from the licence shown at selection.

## Constraints

Accepted 2026-10-25 on the owner's first-hand rulings in conversation, recorded as R1 to R6 and sharpened below. The commitments are binding. Text marked as a hypothesis in Implementation may change within them.

1. **No model definitions in Cadrumo.** No AI model name, digest, size, licence, default, candidate list or ranking exists in any Cadrumo language or file kind: Python, Rust, TypeScript, data files, settings defaults or environment templates. cadrumo-agent's provider catalogue is the sole source of providers and models, local ones included. Test fixtures may use obviously synthetic ids. A gate refuses a model-name or digest literal and a model table in shipped sources, and it states where it stops.
2. **The local program stays; its models do not.** The Rust engine keeps installing and supervising the pinned Ollama program at the managed loopback address. Program archive pins stay, because the program is a component, not a model. The engine pulls whichever model the person selected for a local role. Integrity is Ollama's content-addressed manifest. Cadrumo pins no model digest.
3. **One dispatch path.** Every tax model call goes through the agent service to a cadrumo-agent background run: vision transcription, text extraction, column-role mapping and supply-nature proposal, and the classification and statement-reading callers that use those roles. Cadrumo's direct Ollama adapter `LocalAdapter` and the `LLMProvider.LOCAL` dispatch are deleted. PDF rasterisation stays on Cadrumo's side.
4. **Consent follows a typed flag.** The local lane runs on this host. Whether a catalogue lane sends material off the host is the catalogue entry's typed `reads_off_host` field. It is never inferred from a transport, a provider id or a path. A lane with `reads_off_host` true needs the digest-bound, per-invocation consent of `2026-06-10-llm-evidence-classification-adr`, unchanged. A lane with it false needs no off-host consent. A catalogue entry without the field is refused as an unknown lane, not read as on-host.
5. **Licence is shown, the person decides.** The catalogue entry's licence is shown wherever a model is selected. Cadrumo applies no commercial-use gate and no licence default.
6. **Per-role selection.** The person picks a lane and a model for each role from the catalogue. The choice is stored in the per-profile provider settings in the agent service. `ModelRunService.lookup(role)` selects by role. When the role has no selection it refuses with the typed `NO_SELECTION` code, and it never falls back to another lane or to a default selection. The vision role accepts only a model the catalogue marks vision-capable. A recommended entry from cadrumo-agent may be offered at selection. It is never applied silently.
7. **Catalogue contract.** Cadrumo consumes cadrumo-agent's new catalogue schema version and its typed fields: vision, installed, size_bytes, context_length, licence and reads_off_host. It also consumes the keyless loopback auth kind, a cadrumo-agent-owned recommended set, and the run options temperature, maximum output tokens, num_ctx and response format. Cadrumo does not default or rank any of them. Work that needs the new shape waits for cadrumo-agent to deliver it.
8. **Admission reads the catalogue.** Hardware and contention admission stays. It reads the model's size from the selected catalogue entry (`size_bytes`), not from a Cadrumo table.
9. **Engine input is the selection, not a lookup.** The Rust engine does not read the agent service. The component commands accept the selected local models from their caller as role, model-name and catalogue `size_bytes` triples. The plan digest binds all three. The plan size and the hardware check use the caller's `size_bytes`; the engine invents none. The caller reads the selection from the per-role store.
10. **No fallback, no silent default.** A missing selection, an uninstalled local model or an unavailable lane refuses with a typed verdict that names the selection or setup action. It does not choose another lane, another role's model or a recommended entry.

## Implementation

We will make cadrumo-agent's catalogue the only definition of models, store the per-role choice in the agent service, route every tax model call through the agent, and delete Cadrumo's model tables, pins, settings, ranking and direct local adapter. The sequence is in `2026-10-25-agent-owned-models-plan`.

Outline:

- The agent service stores one selection per role per profile, beside the provider records, and exposes it on the typed wire to the desktop, TUI and CLI. `ModelRunService.lookup(role)` reads it.
- `src/cadrumo_agent_service/providers/domain/catalog.py` moves to the new schema version once cadrumo-agent delivers it. It admits the keyless loopback auth kind and reads the typed fields.
- `ModelRole` stays as the role vocabulary (`src/cadrumo/core/model_catalogue.py:80`). The tables around it are deleted, and the enum moves to a module that holds only roles.
- The Rust engine drops model pins. Its `plan` and `setup` commands take the selected local models, pull each through the server it supervises, and report a row from the selection and Ollama's installed list. Program pins, supervision and the managed loopback address are unchanged.
- Selection surfaces on the desktop, TUI, CLI and MCP show licence, vision capability and the recommended entry. Documentation, environment templates and the four-language locale catalogues follow.

Hypotheses that may change within the constraints:

- The exact wire names of the selection records.
- Whether the engine receives the triples as command arguments or as a protocol field.
- Whether the module holding `ModelRole` is new or an existing one.
- Whether the recommended entry is shown as a button or a pre-filled, unconfirmed choice.

## Rationale

The owner's rulings make one source of models and one dispatch path the only arrangement without a Cadrumo-side model definition. cadrumo-agent already carries providers, models, credentials and background runs, so adding an `ollama` provider there keeps every lane in one catalogue and one run path. A typed `reads_off_host` flag keeps consent correct once local reads leave the direct adapter. Selecting per role is what `lookup` already pretends to do (`del role`), so the fix is the missing store, not a new concept. Ollama's manifest check removes the only reason for a Cadrumo-side digest.

## Consequences

- A person sets up a local role by choosing a model from the catalogue, then approving the pull. Until a role has a selection, its calls refuse `NO_SELECTION`. A fresh installation has no model preselected anywhere in Cadrumo.
- Local reading depends on a signed-in profile and an admitted agent service, as hosted reading already does (`2026-10-19-provider-settings-tax-model-runs-adr` consequences). A source checkout with no service refuses `service_unavailable` for local reads too.
- Model quality baselines named in older records stop being Cadrumo defaults. The licence axis moves from a Cadrumo gate to a displayed fact.
- The Rust engine and the desktop lose their model pins and fixtures. Anything that needed a pinned model digest in a test uses a synthetic id.
- The dev pin generator and the `pin-local-ai` recipe go. Ollama program pins keep their generator.
- Phases that depend on the new catalogue shape wait on cadrumo-agent. The independent preparation can land first.
- Reconsider if cadrumo-agent cannot report installed state or size for a local model, if Ollama stops publishing manifests that verify layers, or if the owner wants a Cadrumo-recommended model again.

## Amended rulings

Basis: the owner's rulings of 2026-10-25, first-hand in conversation. Each accepted record below receives a dated "Amendment 2026-10-25" section appended to its body. The earlier text is kept as history. Proposed records receive a short note only.

### `2026-10-24-rust-component-provisioning-adr`

- **Constraint 3 (unchanged contracts).** The item ids `browser` and `local_ai` and their recovery actions stay. Added: the `local_ai` item is the program plus the models the person selected for local roles. With no local selection the item is the program alone.
- **Constraint 5 (pins are data).** Replaced by: "The browser archive pins and the local AI program pins are declarative data staged into the package. The local AI pins cover the program archive per platform only. They carry no model name, digest, size or licence, and Python reads no role defaults from them. Regenerating program pins stays a developer tool under `dev/`."
- **Constraint 7 (local AI program).** Unchanged. Added: a system-installed Ollama is still detected and never modified, and the managed server is the one the cadrumo-agent `ollama` provider connects to.
- **Constraint 8 (models).** Replaced by: "Rust pulls each model the person selected for a local role, through the pull endpoint of the server it supervises, with byte progress. The names come from the caller as role, model-name and catalogue `size_bytes` triples. Integrity is Ollama's content-addressed manifest. Cadrumo compares no digest to a pin. A model missing from Ollama's installed list is `absent`, a failed pull is `failed`, and there is no digest-based `stale`. The full check is a one-token generation on that server. Role fitness is not component state."
- **Constraint 9 (hardware floor).** Replaced by: "Rust decides `blocked hardware` from total memory and, on NVIDIA, VRAM, against the `size_bytes` of the selected model's catalogue entry. A computer with no selected local model is not blocked. No floor table carries model figures."
- **Constraint 12 (removed Python).** The last sentence, "Load, unload and the fitness probe stay in Python as consumption", is replaced by: "Hardware and contention admission stays in Python and reads size from the catalogue entry. The direct load, unload and fitness probe that go through `LocalAdapter` are deleted with it."

### `2026-10-18-dependency-provisioning-unified-setup-adr`

- **D1 and the 2026-10-19 amendment, ruling 1.** "`local_ai` is the program and the model each catalogue role reads with" is replaced by: "`local_ai` is the program and the model the person selected for each local role. The parts of its plan are the program, then one pull per selected local model not yet installed. There is no catalogue role list in Cadrumo."
- **D7 (verification).** "The catalogue gains an expected digest per model. When the installed digest differs ... `stale`" is withdrawn. Replaced by: "A local model's integrity is Ollama's content-addressed manifest. Cadrumo keeps no expected digest, and a model has no digest-based `stale` state."
- **D8 and the 2026-10-19 amendment, ruling 1.** "`--model` still names one catalogue model for every role" is replaced by: "`aeat config provision pull` sets up the program and the models in the per-role selection. `--model` is removed, because the selection is the only input."
- **D13 scope.** "a Cadrumo-owned model runtime" stays out of scope as narrowed on 2026-10-24. Added to the out-of-scope list: any Cadrumo-defined model.

### `2026-10-19-provider-settings-tax-model-runs-adr`

- **Constraint 1 (retirement).** "`LocalAdapter` stays." is replaced by: "`LocalAdapter` and the `LLMProvider.LOCAL` member are deleted, with their tests and the four local-model settings and their defaults."
- **Constraint 2 (one agent adapter).** "`LLMProvider` keeps `LOCAL` and gains one off-host member for cadrumo-agent." is replaced by: "`LLMProvider` has the one agent member. Every consumer, local or hosted, reaches a model through it." The consumers list gains statement reading.
- **Constraint 5 (service handler).** "a per-`ModelRole` selection when one exists, otherwise the default selection" is replaced by: "the per-`ModelRole` selection the person stored. When the role has none the handler refuses `no_selection`. It does not read a default selection." The sentence "A per-role selection interface is a follow-on and is not part of this record." is withdrawn.
- **Constraint 7 (typed refusals).** "A refusal never falls back to another lane, to the environment or to the on-host model." is replaced by: "A refusal never falls back to another lane or to the environment." `no_selection` now also covers a role the person has not configured, local or hosted.
- **Constraint 8 (consent).** "when it runs off-host" and "Without one they stay on-host or refuse" are replaced by reading the catalogue entry's `reads_off_host` flag. A lane with the flag true needs the token. A lane with it false needs none. The flag is never inferred.
- **Constraint 9 (operation contract).** `ledger.evidence.extract` keeps its single agent choice. The person's choice of lane is the per-role selection. The on-host versus agent switch is removed.
- **Implementation note.** "`role_fitness.py` probes `LocalAdapter` only and is unaffected." is replaced by: "`role_fitness.py` is deleted with `LocalAdapter`."

### `2026-10-13-provider-settings-adr`

- **Former constraint 11, extraction note.** "Cadrumo's own document reading keeps its existing key handling until the owner rules on it" and the historical hold on P03.S12 are closed. The owner ruled: tax model reading goes through the agent, with models and providers from the agent's catalogue. Per-role selection is stored beside the provider records in the service. No Cadrumo-side model list exists.

### `2026-06-13-llm-evidence-classification-adr`

- **Constraints and Implementation.** The setting `aeat_llm_ollama_vision_model` and its default `qwen2.5vl:3b` are deleted. The tiering text (3b default, 7b upgrade, moondream fallback) no longer describes the product. The vision model is the one the person selects for the vision role from the agent's catalogue, and it must be marked vision-capable. The "operator must `ollama pull`" prerequisite becomes the local AI setup pull of the selected model.

### `2026-08-07-unstructured-document-ingestion-provisioning-adr` (proposed)

- **Note only.** D4 (the typed model catalogue and licence-aware selection) is superseded in substance. The catalogue now lives in cadrumo-agent, selection is the person's per role, and licence is shown, not gated. D2 and D3 (hardware and contention) stand, reading size from the catalogue entry.

### `2026-10-13-application-distribution-native-bundle-llm-extra-adr`

- **Constraint "No model weights enter any artifact" and the Implementation verification.** Stand. The verification sentence "`ledger.classify.review` runs past `ledger.llm.acquire` against a locally provisioned model" is read as a model the person selected and the engine pulled. The "local inference closure" language no longer implies a Cadrumo-owned adapter: local reads go through the agent.

### `2026-10-13-agent-attachments-adr`

- **Constraint 7 (eligibility and lanes).** "Local model reading needs no external-disclosure grant." is replaced by: "A lane whose catalogue entry sets `reads_off_host` false needs no external-disclosure grant. A lane with it true does. The flag is typed catalogue data, not inferred from a transport." The "A model the person runs on this machine needs no grant" sentence in the historical text reads the same way.

## Amendment 2026-10-25

Basis: the owner's first-hand ruling in conversation on 2026-10-25, "Choice can go to the encrypted storage, good call" and "I approve".

- **Constraint 6 (per-role selection), storage.** "The choice is stored in the per-profile provider settings in the agent service." is replaced by: "The choice is stored in the agent service's own encrypted per-profile record capability, `model-role-selections`, in its own secure-object namespace `cadrumo.model_role_selections`. It is not a provider-settings record. Changing a role's model therefore never moves the provider-settings generation and never replaces the running agent tree."
- **Capability identity.** The capability mirrors provider settings: a runtime descriptor entry with its own namespace, schema version 1 and classification, one fixed record key, the read, write, delete and generation actions, encryption under the profile key and revision-guarded compare-and-swap. Access is bound to the exact admitted service session and lease, as for provider settings.
- **States.** Absent means no role is selected. A record that does not decrypt or validate is unreadable, never absent, and only a guarded reset removes it.
- **No migration.** The reserved provider-settings key that held the selections on 2026-10-25 never shipped. It is dropped without a migration.
- **Implementation outline.** "The agent service stores one selection per role per profile, beside the provider records" reads as: in a capability of its own, separate from the provider records.
