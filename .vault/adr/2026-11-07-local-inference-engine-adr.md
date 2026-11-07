---
tags:
  - '#adr'
  - '#local-inference-engine'
date: '2026-11-07'
modified: '2026-11-07'
body_schema: 'body-v2'
body_hash: 'sha256:2b9160fb616c37711e7225ac8453b943d3a65615592ea1d537427bb21fe07dc5'
related:
  - "[[2026-11-07-local-inference-engine-research]]"
  - "[[2026-10-24-rust-component-provisioning-adr]]"
  - "[[2026-10-25-agent-owned-models-adr]]"
  - "[[2026-10-18-dependency-provisioning-unified-setup-adr]]"
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-17-single-binary-process-tree-adr]]'
---

# `local-inference-engine` adr: `Add llama.cpp as a second local inference engine` | (**status:** `proposed`)

## Problem Statement

Cadrumo's local reading runs on one engine, the pinned Ollama program. The operator ruled that Ollama stays and that llama.cpp's `llama-server` is added as a second local engine. Nothing is removed or superseded. This record decides how a second engine fits the accepted provisioning, model-ownership and setup commitments. It references `2026-10-24-rust-component-provisioning-adr`, `2026-10-25-agent-owned-models-adr` and `2026-10-18-dependency-provisioning-unified-setup-adr` without amending any of them. Evidence is in `2026-11-07-local-inference-engine-research`. Its measurement section is still pending.

## Considerations

- Most native provisioning code is engine-neutral. The Ollama coupling sits in the pin parser's program check, the model puller and the server start (research, native coupling).
- llama-server's archives are 17-38 MB on the Vulkan, Metal and CPU backends. Ollama's Windows archive is 1.6 GB (research, llama.cpp and Ollama).
- llama-server fixes the context size when a model loads, while cadrumo-agent owns `num_ctx` as a run option (`2026-10-25-agent-owned-models-adr` constraint 7).
- Ollama runs multimodal models on its own engine, so an Ollama vision blob may not load in llama-server. The measurement pass answers this.
- Local model runtimes stay external programs (`2026-10-17-single-binary-process-tree-adr` constraint 7).

## Considered options

- **One cadrumo-agent lane per engine, `ollama_api` and `llamacpp_api`; llama.cpp provisioned as its own optional component item; models acquired once through Ollama's store.** Chosen.
- **An installation-wide engine switch in provisioning state.** Rejected. Provisioning would then decide agent behaviour, and the person's lane and model pick already expresses the choice (`2026-10-25-agent-owned-models-adr` constraint 6).
- **One local lane with an engine sub-option.** Rejected. Each engine has a different API, capability probe and residency protocol. One lane would hide which one failed.
- **Replace Ollama with llama.cpp.** Rejected by the operator's ruling.
- **vLLM.** Rejected. It has no native Windows build, needs Python and PyTorch, and preallocates VRAM.
- **Let llama-server fetch models itself through `-hf`.** Rejected. The download would bypass Rust ownership, the plan-bound approval and the declared hosts.
- **Build llama.cpp, or bundle it in the installer.** Rejected. Cadrumo builds no model runtime, and one pinned download path per program keeps backend selection per machine.

## Constraints

1. **Lanes and selection.** cadrumo-agent owns a `llamacpp_api` lane beside `ollama_api`. It is keyless, at a loopback address, with `reads_off_host` false and its own model list. The person chooses an engine only by turning lanes on and picking a model. No Cadrumo setting, environment variable or component state selects an engine.
2. **The lane's protocol.** The lane speaks the OpenAI-compatible `/v1` API. Residency goes through router mode's `/models`, `/models/load` and `/models/unload`. Capabilities come from declared catalogue metadata plus `/props` (`modalities`, `n_ctx`, `chat_template`), never from `/api/show`.
3. **Admission stays with cadrumo-agent.** It admits each load on either engine, including memory contention between the two servers, and refuses with `model_does_not_fit`. Cadrumo adds no admission. Tension: Ollama takes `num_ctx` per request, while llama-server fixes the context at load. Reconciliation: Cadrumo launches llama-server with no context-size or other model-specific argument, and the context for a load comes from cadrumo-agent. A different context means a reload, which the lane admits like any load.
4. **Component.** The llama.cpp program is a new item, `local_ai_llamacpp`, enrolled under the unified-setup D1 enrolment clause, with its own writer lock, plan, approval, receipt, states, failure categories and `desktop.setup` wording. The `local_ai` item keeps its exact meaning: the Ollama program and the model a desktop download names. llama.cpp is optional. Setup is complete when `browser` and `local_ai` are ready, as D2 and D11 state. Tension: D1 and constraint 3 of the provisioning ADR enumerate two items. This record adds a third and leaves those two unchanged.
5. **Program pins.** `native/component-pins/local_ai_llamacpp_program.toml` pins one build tag. For each platform and backend it declares the URL, format, executable path, size and SHA-256. The pin schema is per program: the parser validates each program's own identity and version grammar instead of `program == "ollama"` (`native/application/src/provisioning/pins.rs:252`). The pin files carry no model data. Their generator follows `dev/env/local_ai_pins.py` under `dev/`.
6. **Backend policy.** Windows and Linux default to Vulkan. macOS arm64 uses the Metal build. A machine where the Vulkan loader is absent, or where the full check fails on Vulkan, falls back to the CPU build. Rust chooses the backend from a hardware probe at plan time, the plan digest binds the choice, and the receipt records it. CUDA, ROCm and SYCL are not pinned now. A platform with no pinned archive reads `blocked not_in_this_build`.
7. **Process.** The runtime manager hosts llama-server through the existing `ServerSupervisor` restart policy and containment, independently of the Ollama server. It has the same lifecycle and the same lack of custody authority as the Ollama server (`2026-10-04-runtime-manager-architecture-adr`, local AI server section). It listens on a second fixed loopback address, `local_ai_llamacpp_address`, declared once in `native/application-environment.toml`. That address is distinct from Ollama's `127.0.0.1:23743` and from llama-server's upstream default port. The agent service passes it to cadrumo-agent as a lane base URL. Readiness is `/health` answering 200, and the quick check is that same probe.
8. **Model acquisition and integrity.** Models are fetched only by Rust, at setup, through a digest-bound plan the person approves. Weights are never bundled. The leading path keeps the current pull: the Ollama server the manager supervises fetches from its registry into `models/ollama`, under the `local_ai` writer lock, and Ollama's content-addressed manifest stays the integrity check. llama-server then reads the same verified GGUF layers read-only, so one store serves both engines. Rust derives the router's model entries at run time from the installed manifests' model and projector layers. Model names therefore appear only as data read from the store, never as a literal in Cadrumo. Removing a model first unloads it from llama-server, and router entries are regenerated after each pull or removal.
9. **No model definitions.** Cadrumo defines no model names, digests, sizes or artefacts for either engine. cadrumo-agent's catalogue declares, per engine, which artefacts a model needs on that lane. A download started from the `llamacpp_api` list is admitted by the desktop host exactly as the provisioning ADR's constraint 2 and the model-ownership ADR's constraint 9 describe.
10. **Python** provisions, probes and launches nothing for llama.cpp. The no-Python-provisioning and no-model-definitions gates extend to llama.cpp terms.

## Implementation

We will add llama.cpp as an optional second local engine. It gets its own pinned, Rust-provisioned component item, its own managed server on a fixed loopback address and its own cadrumo-agent lane, and it reads the models Ollama's store already verifies. Ollama's item, lane, pins, address and pull path stay exactly as they are.

Hypotheses, free to change within the constraints:

- The address value. `127.0.0.1:23744` is the candidate, subject to the same IANA and ephemeral-range check as `local_ai_address`.
- How cadrumo-agent supplies the context for a load. The candidate is a per-load argument on `/models/load`. Router presets are documented, but per-load arguments are not (research, llama.cpp). If the pinned build lacks them, the fallback is a manager-launched single-model process per admitted load, with the context passed through a typed request from the agent service. That fallback needs its own evidence before it is adopted.
- Router flags. `--no-models-autoload` and `--models-max 1` are the candidates, so that no load happens without cadrumo-agent's admission and no least-recently-used eviction acts behind it.
- Whether router entries are a generated `--models-preset` file or links under a `--models-dir`. Either is regenerated from the installed manifests. Whether llama-server accepts an extensionless `sha256-<digest>` blob is unmeasured.
- Fallback acquisition A: a Rust registry client that fetches the same registry manifest and verifies each layer's SHA-256 against that manifest before writing into the same store, under the `local_ai` lock. Integrity remains the content-addressed manifest, and no digest is compared to a pin.
- Fallback acquisition B, for vision only: if Ollama's vision blobs do not load in llama-server, a Hugging Face GGUF plus its `mmproj` file. cadrumo-agent's catalogue would declare the artefact per engine. The download hosts would be declared, the publisher's file SHA-256 would be bound into the plan digest, and the files would be stored under `models/llamacpp`. This path adds hosts and a second store, so it is adopted only on measurement evidence.
- Archive formats, the macOS code-signing and quarantine handling, and the exact Vulkan probe.

## Rationale

One lane per engine keeps the choice where `2026-10-25-agent-owned-models-adr` already puts it, in the person's lane and model pick, and keeps each engine's probe, residency and refusals separate. A separate optional item keeps every word of the accepted `local_ai` item true and keeps the hard-requirement rule intact, while D1's enrolment clause admits the new dependency. Reading Ollama's verified store keeps one acquisition path, one approval, one set of hosts and one integrity anchor. It adds no second copy of multi-gigabyte weights. Vulkan, Metal and CPU archives are tens of megabytes and cover NVIDIA, AMD and Intel GPUs without vendor runtimes. CUDA can follow once the GPU pass shows its gain.

## Consequences

- People can run local models on a 17-38 MB engine with broad GPU coverage. Ollama stays available and required.
- The `llamacpp_api` lane depends on the Ollama program for acquisition under the leading path. A llama.cpp-only installation is not a goal of this record.
- Two servers can each hold a model. cadrumo-agent's admission must account for both, or memory refusals will come from the server rather than from admission.
- Under constraint 3, a context change costs a reload on llama-server.
- Vulkan VRAM is not probed, so the hardware floor stays on total memory and NVIDIA VRAM (D14). Load failure on other GPUs surfaces as `model_does_not_fit`.
- Verification:
  - Pin parser and generator tests per program and backend.
  - A fake llama-server beside `native/application/src/provisioning/local_ai/fake_ollama.rs`, covering `/health`, `/props`, router load and unload, and failure.
  - Supervision and containment tests for two concurrent servers.
  - The extended Python and model-definition gates.
  - A packaged lane proof in cadrumo-agent binding `binary="llama-server"`, with a real text turn and, if vision loads, a real vision turn.
  - The CPU measurement pass. The RTX 4080 SUPER pass runs only once coordinated with the desktop build.
- Reconsider if Ollama's store format stops being GGUF that llama-server can read, if llama.cpp stops publishing per-backend archives, if router mode changes its residency contract, or if the operator wants llama.cpp to be sufficient without Ollama.
