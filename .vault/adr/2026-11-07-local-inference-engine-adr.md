---
tags:
  - '#adr'
  - '#local-inference-engine'
date: '2026-11-07'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:53a260538534a187a8e05de1eb86a07b58e331f7240dbdecda9ed5695e06ace7'
related:
  - "[[2026-11-07-local-inference-engine-research]]"
  - "[[2026-10-24-rust-component-provisioning-adr]]"
  - "[[2026-10-25-agent-owned-models-adr]]"
  - "[[2026-10-18-dependency-provisioning-unified-setup-adr]]"
  - '[[2026-10-04-runtime-manager-architecture-adr]]'
  - '[[2026-10-17-single-binary-process-tree-adr]]'
  - '[[2026-11-07-local-inference-engine-audit]]'
  - '[[2026-10-13-provider-settings-adr]]'
---

# `local-inference-engine` adr: `Bundle llama.cpp as the default local inference engine and keep Ollama as a selectable second engine` | (**status:** `accepted`)

## Problem Statement

Cadrumo's local reading runs on one engine, the Ollama program that Rust downloads at setup. The operator ruled on 2026-11-07:

> "llama.cpp is the primary engine and is prebundled in the native cadrumo - ollama support remains. Needs backend engine picking. The responsibility is yours to build out the backend per lane (ollama is already working!). llama.cpp becomes dependency and default. Agent settings needs local llm setting switch. Model acquisition mechanism needs adjusting internally but ux should be identical regardless."

The operator added the same day: the frontend stays largely unmodified, and only internal defaults change and an engine switch is added. With llama.cpp selected, nothing downloads, starts or requires Ollama. The operator also asked whether a person should pick GPU or CPU models. That design choice was delegated to this record (D6).

This record decides how llama.cpp becomes the bundled default engine, how a person picks the engine, how models are acquired for both engines, and how device placement works. It replaces this record's earlier draft, which made llama.cpp an optional downloaded item. Evidence, including the CPU measurement pass, is in `2026-11-07-local-inference-engine-research`. The Ollama lane defect the pass exposed is in `2026-11-07-local-inference-engine-audit`.

## Considerations

- Most native provisioning code is engine-neutral. The Ollama coupling sits in the pin parser's program check, the model puller and the server start (research, native coupling).
- llama-server's Windows Vulkan archive is 37.7 MB zipped, 105.8 MB unzipped. Ollama's Windows archive is 1.59 GB zipped, 2.23 GB unzipped (research, CPU pass).
- Ollama's `qwen3:1.7b` text blob loads in llama-server b12184 in place. Ollama's single-GGUF `qwen3-vl:2b` vision blob does not. `qwen3-vl:4b-instruct` ships a separate projector layer. A Hugging Face Qwen3-VL-2B GGUF plus mmproj read the synthetic invoices at 1.0 schema-valid and 0.95 field accuracy on CPU (research, CPU pass).
- llama-server takes its context size from the model when none is given. For `qwen3:1.7b` that is 40960 tokens over 4 slots (research, CPU pass). cadrumo-agent owns `num_ctx` as a run option (`2026-10-25-agent-owned-models-adr` constraint 7).
- Local model runtimes are external programs with their own process tree (`2026-10-17-single-binary-process-tree-adr` constraint 7). The native build already pins third-party inputs by digest, for example the CPython distribution in `native/toolchain.json:11`.
- A few sentences of accepted provisioning text are Ollama-specific (Reconciliation, below).

## Considered options

- **Bundle llama-server in the native package as the default engine; keep Ollama as a selectable, downloaded second engine; one local engine setting; one Rust-owned model store for both.** Chosen, on the operator's ruling.
- **Make llama.cpp an optional downloaded component item.** Rejected by the operator's ruling that llama.cpp is prebundled and the default.
- **Replace Ollama with llama.cpp.** Rejected by the operator's ruling that Ollama support remains.
- **vLLM.** Rejected. It has no native Windows build, it needs Python and PyTorch, and it preallocates VRAM through `gpu_memory_utilization`. It fits neither Rust-only provisioning nor a shared desktop GPU.
- **One local lane with an engine sub-option.** Rejected. Each engine has its own API, capability probe and residency protocol. One lane would hide which engine failed.
- **Let llama-server or Ollama fetch models themselves (`-hf`, `/api/pull`).** Rejected. The fetch would bypass Rust ownership, or it would require Ollama when llama.cpp is selected.
- **Bundle CUDA builds.** Rejected for now. The Windows CUDA 12.4 archive plus cudart is 680 MB zipped. A CUDA build can follow as an optional download once the GPU pass shows its gain.
- **Separate GPU and CPU model lists, or per-model GPU and CPU variants.** Rejected (D6). The same GGUF serves both devices, so variants duplicate downloads and confuse the list.
- **Fall back to CPU silently when a GPU load does not fit.** Rejected (D6). It hides a performance cliff and contradicts the no-silent-substitute rule of `2026-10-25-agent-owned-models-adr` constraint 10.

## Constraints

### D1. Engine set and default

- llama.cpp's `llama-server` is the primary and default local engine.
- Ollama remains a supported second engine.
- vLLM is not an engine, for the reasons above.

### D2. Bundling

- llama-server is a native package dependency. The CMake build stages it from a pinned upstream llama.cpp release. Each platform's archive is pinned by build tag, size and SHA-256, the way the build pins its other third-party inputs. Package assembly refuses an archive that does not match its pin. Cadrumo does not build llama.cpp.
- Backend policy:
  - Windows x64 and Linux x64 ship the Vulkan build, which includes the CPU backends.
  - macOS arm64 ships the Metal build.
  - A target with no Vulkan build ships the CPU build.
  - CUDA is not bundled. It is a possible later optional download.
- llama-server is installed with the package. It needs no setup item, no plan and no download approval.
- Model weights are never bundled.
- llama-server runs as its own process under the runtime manager. It is an upstream binary, not a Cadrumo binary, and it stays an external program under `2026-10-17-single-binary-process-tree-adr` constraint 7.

### D3. Engine selection

- cadrumo-agent backs the local model experience per lane. The `ollama_api` lane exists and stays. cadrumo-agent adds a llama.cpp lane that speaks llama-server's OpenAI-compatible `/v1` API and router endpoints. The lane is keyless, at a loopback address, with `reads_off_host` false.
- One "local engine" setting in agent settings selects which engine backs the local model experience. Its values are `llamacpp` and `ollama`. The default is `llamacpp`.
- The agent service persists the setting in its provider-settings custody (`2026-10-13-provider-settings-adr` constraints 2 and 3). The record carries schema identity, the engine, the placement (D6), a generation and the update time. An absent record means the defaults. A corrupt, unreadable or stale record refuses and never means the defaults.
- The experience is identical regardless of engine: the same model list, download flow, progress, admission refusals and wording. The backend serves every word, and the frontend renders it. The frontend gains only the engine switch, whose words the backend also serves.
- Switching engines retires the exact-session agent tree, as a provider-settings generation change already does (`2026-10-13-provider-settings-adr` constraint 9).
- With `llamacpp` selected, nothing downloads, starts or requires Ollama.
- Ollama is downloaded only when the person selects the `ollama` engine and approves its setup. Its program item, pins, writer lock and approval are as `2026-10-24-rust-component-provisioning-adr` constraint 7 describes.

### D4. Model acquisition, adjusted internally

- Rust owns all model fetching for both engines. Neither engine's server fetches a model.
- Text models: Rust fetches Ollama-registry manifests and blobs itself, without a running Ollama. It verifies each layer's SHA-256 against the manifest in Rust and writes the Ollama store layout (`manifests/`, `blobs/sha256-*`). One store serves both engines. llama-server reads the blobs in place, and Ollama can still use the store.
- Vision on llama-server has two routes:
  - **Route A, registry projector.** A registry tag that ships a llama.cpp projector layer (`application/vnd.ollama.image.projector`), as `qwen3-vl:4b-instruct` does. Rust fetches it like any other tag, and llama-server loads the model layer with the projector layer as its mmproj.
  - **Route B, Hugging Face GGUF plus mmproj.** cadrumo-agent's model catalogue declares a Hugging Face GGUF and its mmproj file, each digest-pinned by cadrumo-agent. Rust fetches both from declared hosts, verifies them against those digests, and writes them into the same content-addressed store.
  - Both routes are admitted. The GPU pass decides which route cadrumo-agent's catalogue uses by default for each recommended vision model. That choice is recorded as an amendment to this record.
- Cadrumo still defines no model name, digest, size or artefact. cadrumo-agent's catalogue declares, per engine, which artefacts a model needs. A model the catalogue recommends has a route on both engines, so the list does not change with the engine.
- Integrity means content digests, verified by Rust for both engines: the registry manifest's layer digests, or the digests cadrumo-agent's catalogue declares for a Hugging Face file. No model digest is compared to a Cadrumo pin.
- The desktop download flow, the `admit_local_ai` admission, the plan digest and the approval stay as `2026-10-24-rust-component-provisioning-adr` constraints 2 and 8 and `2026-10-25-agent-owned-models-adr` constraint 9 describe, apart from the reconciled sentences below.

### D5. Context, admission and process

- cadrumo-agent always passes an explicit context size for a llama-server load: `-c`, or `ctx-size` in the model's router preset entry. It never relies on llama-server's full-context default.
- cadrumo-agent admits every load on either engine and refuses a load that cannot fit with `model_does_not_fit`. Cadrumo adds no admission.
- Python provisions, probes and launches nothing for either engine. The no-Python-provisioning and no-model-definitions gates extend to llama.cpp terms.
- The runtime manager supervises llama-server through the existing `ServerSupervisor` restart policy and containment. llama-server listens on one fixed loopback address, `127.0.0.1:23744`, declared once in `native/application-environment.toml` beside Ollama's `127.0.0.1:23743`. The agent service passes it to cadrumo-agent as the lane's base URL. Readiness is `/health` answering 200.
- llama-server runs in router mode. Loads and unloads go through `/models/load` and `/models/unload`, under cadrumo-agent's admission.

### D6. Device placement

- There are no separate GPU and CPU model lists. The same GGUF serves both.
- Placement is an engine-launch policy in the same local engine setting. Its values are `auto` (the default) and `cpu_only`.
  - `auto`: llama-server offloads layers to a Vulkan or Metal device when one is present and the load fits. cadrumo-agent's admission picks the offload (`-ngl` or the fit options). Ollama uses its own device detection.
  - `cpu_only`: llama-server runs with `-ngl 0`. Ollama runs with `num_gpu 0` or its CPU library.
- The hardware floor and cadrumo-agent's admission account for the placement. Under `cpu_only` the floor uses total memory only.
- The backend serves the placement words.
- A refused fit stays a typed refusal, `model_does_not_fit`. It never falls back to CPU silently.

## Reconciliation with accepted records

Accepted text that this record leaves unchanged:

- `2026-10-18-dependency-provisioning-unified-setup-adr`, the rejected option "Bundle Chromium and model weights in the installer", and D14's "bundling browsers or models in the package". Both cover Chromium and model weights. llama-server is neither, and weights stay unbundled (D2).
- The same record's rejected option "Let Cadrumo build its own model runtime binary", and D14's "a Cadrumo-built model runtime". Cadrumo stages a pinned upstream release and builds nothing (D2).
- The same record's D14 exclusion "installing the model runtime on Linux, which keeps its plain instruction". It still governs Ollama. Setup does not install the packaged llama-server.
- `2026-10-24-rust-component-provisioning-adr` constraint 7. Rust still downloads Ollama's pinned archive, now only after the person selects the `ollama` engine (D3).
- `2026-10-17-single-binary-process-tree-adr` constraint 7 (D2).
- `2026-10-25-agent-owned-models-adr` constraints 6, 7 and 10. Each local lane keeps a model list. `num_ctx` remains a run option, which the llama.cpp lane turns into a load context (D5). No engine or device stands in silently (D6).
- `2026-08-07-unstructured-document-ingestion-provisioning-adr` (proposed), the constraint "no model bytes, no runtime binaries in any wheel". llama-server enters the native package, not a Python wheel, and the tax engine still has no local-inference install option.

Accepted sentences that contradict this decision, with the amendment each needs. This record flags them for approval together with it. It does not apply them.

1. `2026-10-18-dependency-provisioning-unified-setup-adr` D1, second bullet. Current: "`local_ai` is the Ollama program plus the one model a desktop download names from the person's local model list; the program and that model are its parts, never items of their own." Proposed: "`local_ai` is the selected local engine's program plus the one model a desktop download names from the person's local model list; the program and that model are its parts, never items of their own. The packaged llama-server program is part of the installation and is never downloaded (`2026-11-07-local-inference-engine-adr` D2)." Reason: without this change, the D11 hard requirement would require the Ollama program under the default engine.
2. `2026-10-24-rust-component-provisioning-adr` constraint 3. Current: "The `local_ai` item is the Ollama program, plus the one model a desktop download names; a setup, check, verification or removal that names no download is the program alone." Proposed: "The `local_ai` item is the selected local engine's program, plus the one model a desktop download names; a setup, check, verification or removal that names no download is the program alone. The packaged llama-server program reads ready from the installation and is never downloaded."
3. `2026-10-24-rust-component-provisioning-adr` constraint 8.
   - Current: "Rust pulls the model a desktop download names, through the pull endpoint of the server the manager supervises, with byte progress." Proposed: "Rust fetches the model a desktop download names from its registry or declared source itself, with byte progress. It verifies each layer's SHA-256 and writes the Ollama store layout, and no local model server runs to acquire the model."
   - "its pull progress follows the totals the server streams" becomes "its progress follows the sizes the fetched manifest declares".
   - "Integrity is Ollama's content-addressed manifest, and Cadrumo compares no digest to a pin" becomes "Integrity is the content digests of the registry manifest or of cadrumo-agent's catalogue, verified by Rust, and Cadrumo compares no digest to a pin".
   - "A model missing from Ollama's installed list is `absent`" becomes "A model whose manifest is missing from the store is `absent`".
   - The full check runs "on the selected engine's server".
4. `2026-10-24-rust-component-provisioning-adr` constraint 9. Append: "Under the `cpu_only` placement the floor uses total memory only; the desktop host passes the placement in the admission."
5. `2026-10-24-rust-component-provisioning-adr` constraint 12. Current: "It starts the server whenever the local AI program is installed and verified" and "The server listens on one fixed Cadrumo loopback address". Proposed: "It starts the packaged llama-server whenever the package carries it, and the Ollama server only while the selected engine is `ollama` and the program is installed and verified" and "Each engine's server listens on its own fixed Cadrumo loopback address". Reworded on 2026-11-07 with the coordinating session's approval: only the selected engine's server starts, and the other engine's server never does. The binding text is in that record's amendment.
6. `2026-10-25-agent-owned-models-adr` constraint 9. Current: "pull progress follows the totals the server streams". Proposed: "download progress follows the sizes the fetched manifest declares".

Two optional context edits follow. Neither is binding text. `2026-10-18-dependency-provisioning-unified-setup-adr` Considerations says "Browsers, models and the model runtime are not package data." The edit adds a dated note: "Since `2026-11-07-local-inference-engine-adr`, the llama-server runtime is package data; Ollama, browsers and models are not." `2026-06-13-llm-evidence-classification-adr` Considerations says "Model weights are pulled into the person's own Ollama runtime". The same kind of note applies there: weights are fetched by Rust into a store that either engine reads.

## Implementation

We will:

- stage a pinned llama-server build into every native package;
- add cadrumo-agent's llama.cpp lane and make it the default local engine, behind one agent-settings switch;
- move all model fetching for both engines into Rust, over one content-addressed store;
- keep Ollama as a selectable engine, downloaded only on the person's approval.

Hypotheses, free to change within the constraints:

- The build pin. b12184 is the measured build. The pin's file and format sit with the other build-input pins. They do not go under `native/component-pins/`, which holds the download pins Rust reads at run time.
- How cadrumo-agent's context reaches a router load. The measured route is a preset entry whose `ctx-size` applies at load (research, CPU pass). Per-load arguments on `/models/load` are undocumented. If neither route fits cadrumo-agent's per-turn context, the fallback is a manager-launched single-model process per admitted load, which needs its own evidence first.
- Router flags. `--no-models-autoload` and `--models-max 1` are the candidates. With them, no load happens without admission, and no least-recently-used eviction happens behind admission's back.
- How Hugging Face files enter the store. The candidate is content-addressed blobs plus a manifest under a distinct host namespace. The existing per-model removal rule (remove only the layers that no remaining manifest uses) then still holds.
- How the desktop host tells the manager which engine server to run.
- The Vulkan presence probe, macOS code signing and notarisation of the bundled binary, and the archive format per platform.

## Rationale

The operator ruled the engine set, the default and the bundling. The rest follows from that ruling:

- A 38 MB bundled engine removes the 1.6 GB download from the default path.
- Vulkan and Metal builds cover NVIDIA, AMD, Intel and Apple GPUs without vendor runtimes.
- One lane per engine keeps each engine's protocol, probe and refusals separate, while one setting keeps the person's choice to a single switch.
- A Rust-owned fetch into Ollama's store layout keeps one acquisition path, one approval, one integrity rule and one copy of the weights. It also takes Ollama out of the llama.cpp path.
- Two vision routes keep the measured Hugging Face route available while the GPU pass tests the registry projector route.
- A placement policy, instead of device-specific models, keeps one model list and keeps refusals explicit.

## Consequences

- The default path needs no engine download. Ollama users keep their engine, lane and store.
- The package grows by about 38 MB on Windows, plus the macOS and Linux builds, and package signing covers a third-party binary.
- Rust gains a registry client, Hugging Face source handling and store writing. The provisioning amendments above must be approved before that work executes.
- A context change on llama-server costs a reload.
- Vulkan VRAM is not probed, so the `auto` floor stays on total memory and NVIDIA VRAM. A load that does not fit on another GPU surfaces as `model_does_not_fit`.
- Verification:
  - Build-pin tests per platform and backend, and a package-assembly refusal of a mismatched archive.
  - A fake llama-server beside `native/application/src/provisioning/local_ai/fake_ollama.rs`, covering `/health`, `/props`, router load and unload, and failure.
  - Registry-client tests for layer verification, resume, damaged downloads and the store layout, including a store that Ollama then reads.
  - Engine-switch tests: the tree retires, the setting persists, and with `llamacpp` selected Ollama never starts.
  - The extended Python and model-definition gates.
  - Packaged lane proofs on both engines, each with a real text turn and a real vision turn.
  - The GPU pass on an RTX 4080 SUPER, which settles the default vision route.
- Reconsider if llama.cpp stops publishing per-backend archives, if Ollama's store stops being GGUF that llama-server can read, if router mode changes its residency contract, or if the GPU pass shows a CUDA build is needed by default.

## Authorization basis

The operator gave the ruling quoted in the Problem Statement directly to the orchestrating session on 2026-11-07. In the same session the operator added that the UX stays identical whichever engine serves the models, that acquisition must not need Ollama when Ollama is not selected, and asked whether people should pick between GPU and CPU models; D6 answers that question. The coordinating session confirmed acceptance on the same day. On that basis this record is accepted.

The six reconciliation amendments follow directly from the ruling, which makes llama.cpp the default and drops the need for Ollama when it is not selected. They are applied as the first Step of the implementation plan, and the operator has been told about each one. The GPU pass settles only the default vision route, which will be recorded as an amendment.

## Amendment 2026-11-07: default vision route and the reasoning requirement

Basis: the operator's first-hand ruling of 2026-11-07 recorded above, the coordinator's plan approval of the same day, and the GPU pass in `2026-11-07-local-inference-engine-research` (RTX 4080 SUPER, llama-server b12184 on Vulkan and CUDA, against Ollama 0.40.13). This amendment settles the choice D4 left open and adds one lane requirement. It changes no other constraint.

- **D4, default vision route.** The catalogue chooses the route per model, and Cadrumo still defines no model.
  - A registry tag that ships a llama.cpp projector layer uses Route A: the Ollama-registry model plus projector layers in the shared store. `qwen3-vl:4b-instruct` is the measured case. Both backends loaded it with its projector layer (`projector_route_ok` true on Vulkan and CUDA), at 1.0 schema-valid and 0.95 field accuracy.
  - A registry tag without a llama.cpp projector, such as `qwen3-vl:2b`, uses Route B: the Hugging Face GGUF plus mmproj that cadrumo-agent's catalogue declares and digest-pins. The measured pair is `Qwen/Qwen3-VL-2B-Instruct-GGUF` Q4_K_M plus mmproj Q8_0.
  - A model the catalogue recommends keeps a route on both engines, so the list does not change with the engine.
- **D2, backend.** CUDA stays optional and later. The bundled Vulkan build is sufficient for the default.
- **D3, lane reasoning requirement.** The llama.cpp lane suppresses reasoning for structured extraction, with `--reasoning-budget 0` or per-request reasoning control, whichever the pinned build supports. It refuses a think-only reply with a typed refusal. On b12184, `qwen3:4b` (Qwen3 4B Thinking 2507, from the Ollama blob) ignored `chat_template_kwargs` `enable_thinking:false`, spent 400 tokens thinking and returned only empty answers (schema-valid 0/5). The lane re-runs that measurement cell as acceptance.
- **Known gap.** On the bundled Vulkan build `qwen3-vl:2b` generates at about 128 tok/s, against 261 to 267 tok/s on Ollama and on CUDA, about half. The remedy is the optional CUDA build, later. The gap does not block the 4b vision default.

## Amendment 2026-11-07: Linux source build and the Windows runtime libraries

Basis: the P03.S11 staging findings, approved by the coordinating session on 2026-11-07 under the operator's first-hand ruling recorded above. This amendment is a rollout gap under that ruling, not a reversal of it. llama.cpp stays the default engine, and only the Linux path to it changes. It amends D2 and D1 for Linux and adds one D2 requirement for Windows. It changes no other constraint.

- **Finding.** The pinned b12184 Linux archives (`ubuntu-vulkan`) require `GLIBC_2.34` on x86-64 and `GLIBC_2.38` on arm64, along with `GLIBCXX_3.4.30` / `3.4.32` and `CXXABI_1.3.13` / `1.3.15`. Both also load `libssl.so.3`, `libcrypto.so.3`, `libgomp.so.1` and `libvulkan.so.1` from the host. The package floor is glibc 2.28. Package assembly therefore refuses both archives with a typed glibc-floor error.
- **D2, Linux.** The glibc 2.28 floor stays.
  - On Linux, the native build compiles llama-server from the pinned upstream b12184 source tarball, pinned by size and SHA-256, inside the Linux native build at the 2.28 floor.
  - The build uses the CPU backend, with no OpenSSL and no curl, and links `libgomp` statically. Cadrumo applies no patch and authors no runtime code.
  - The binary stays an upstream program run as its own process, an external program under `2026-10-17-single-binary-process-tree-adr` constraint 7.
  - D2's sentence "Cadrumo does not build llama.cpp" and its "Linux x64 ships the Vulkan build" now apply to Windows and macOS only.
  - Package assembly keeps refusing a Linux binary that exceeds the floor.
- **D1, Linux default.** Until the Linux source build lands and passes the packaged smoke, the Linux package carries no llama-server and Linux keeps `ollama` as its default engine. Windows and macOS bundle llama.cpp as decided. The P05 default flip applies per platform, and on Linux it follows the source-build Step.
- **D2, Windows runtime libraries.** `llama-server.exe` imports `msvcp140.dll` and `vcruntime140_1.dll`, while Cadrumo's own Rust binaries link the C runtime statically.
  - The Windows package stages app-local `msvcp140.dll`, `vcruntime140.dll` and `vcruntime140_1.dll` from the pinned MSVC toolchain's Redist folder into the llama-server directory, hashed in the package manifest.
  - A staging check reads each PE file's import table there. It refuses any import that is neither an operating-system DLL nor present beside the binary. A fixture with a missing DLL proves the refusal.
- **Reconciliation.** Building an unmodified, pinned upstream source tarball on Linux narrows two accepted sentences of `2026-10-18-dependency-provisioning-unified-setup-adr`: the rejected option "Let Cadrumo build its own model runtime binary" and D14's "a Cadrumo-built model runtime". Both are amended there by a dated note.
  - The note says that, since this amendment, Cadrumo compiles the pinned upstream llama-server source on Linux without modification, and builds no runtime of its own.
  - It also records that Ollama is still never built.
  - This record's earlier reconciliation line, "Cadrumo stages a pinned upstream release and builds nothing", is superseded for Linux by this amendment.

## Amendment 2026-11-08: who sets the llama.cpp context and offload

Basis: the coordinator's acceptance on 2026-11-08 of the residency contract settled for P02.S07, which applies rulings already made, recorded here as coordinator-accepted. The evidence is the live b12184 router probe (`llama-server` b12184 in router mode, `--models-preset`, `--models-max 1`, `--no-models-autoload`). This amendment narrows D5 and D6 for the llama.cpp engine. It changes no other constraint, and the Ollama engine is unchanged.

- **Finding.** On b12184 in router mode, a load applies the context and offload the preset section states. `POST /models/load` ignores per-request `args`, `extra_args`, `ctx_size` and `n_ctx`. `/models/add`, `/models/remove` and `/models/delete` answer 404. Each listed model's `status.args` carries the `--ctx-size` and `--n-gpu-layers` it runs with. All four slots receive the full context. With `--fit on`, the default, llama-server fits only the arguments left unset.
- **D5, context on llama.cpp.** cadrumo-agent still owns the context, through its catalogue: the preset's `ctx-size` for a model is the catalogue's `models[].artefacts.llamacpp_default_context`, never a constant. The desktop passes that value with each model download request, Rust records it beside the store manifest, and the manager writes the preset from that record. Rust never parses the agent catalogue. A model with no declared context gets no preset section, so it cannot be loaded.
  - cadrumo-agent addresses a model only by its alias, never writes the preset and never passes a context. It makes the model resident before each request. A run whose first request, or whose stated `context_tokens`, needs more than the model's preset window is refused as `model_does_not_fit` before any prompt is sent. On this engine the window does not grow to fit, and the reply bound fits inside the window instead.
  - The interim fixed `ctx-size` of 8192 in the P03.S17 preset is replaced by this route.
- **D6, offload on llama.cpp.** "cadrumo-agent's admission picks the offload" no longer applies to llama.cpp. The placement is written into the preset by the manager: `cpu_only` writes `n-gpu-layers = 0`, and `auto` writes no key, so llama-server's own launch-time fit chooses the offload. A placement change goes through the manager's drain and restart. cadrumo-agent reads the placement from `status.args` only to word a refusal.
- **Admission mapping.** A load that ends `failed` maps to `model_does_not_fit`. A model the router does not present maps to `model_not_installed`. A model without an explicit context, or a router that cannot be reached, maps to `provider_unavailable`.

## Amendment 2026-11-11: the local AI server starts on demand

Basis: the operator's ruling that local LLM use on the 16 GB reference machine is document extraction and classification only, and the coordinator's rulings of 2026-11-11 under delegated design authority. The evidence is build 15's packaged run, in which the app started `llama-server` at GUI launch with no request. The trace runs `native/manager/src/background.rs` `Background::new` → `LocalAi::start` → `LocalAiHost::at` (`native/manager/src/supervision/local_ai.rs`), whose supervision thread starts the server on its first look. The GUI hosts the manager core at launch, so manager start was server start. The router itself loaded no model (`--no-models-autoload`; the only load is cadrumo-agent's per-request `make_resident`). This amendment changes when the server runs. D5's router mode, addresses, containment and admission are unchanged, and so is the Ollama engine's role, which gets the same lifetime.

- **D5, server lifetime.** At manager start the selected engine's server is *dormant*: the manager's supervision is set up and the program is checked, but no server process runs. "Supervised for the manager's whole life" now means the supervision lives that long, not the process.
- **D5, demand.** The server starts only on a demand. A demand is a manager IPC verb, and its only caller is the agent service, before cadrumo-agent extracts or classifies a document on a local lane. The verb goes through the manager's existing native peer admission: exact process and peer evidence, the agent-service role and invocation. A client-supplied ID grants nothing. The manager starts the server, waits for `/health`, and answers ready or a typed refusal. cadrumo-agent's admission and `make_resident` then load the model, as before. There is no second channel: no lease file, no environment flag, and no direct start by cadrumo-agent. When the agent service cannot reach the manager, the extraction or classification is refused with a reason the backend serves.
- **D5, idle stop.** When the router has held no model for 5 minutes, the manager stops the server through its job (Windows) or process group (Linux, macOS), by its own process ID, back to dormant. A stop never unloads a model in use. Crash restart applies only while the server is demanded and not idle-stopped.
- **D5, what never demands.** GUI launch, manager start, warm-up, status checks, readiness probes, settings pages and setup never start the server. Setup verifies the program without leaving a server running.
- **Served state.** Dormant is a state of its own in the manager's published `ServerState` and in the local AI status the backend serves, with backend words meaning "starts when a document is read". It is never reported as `host_unreachable`, `program_not_running` or unchecked. `program_not_running` and `server_wait_expired` keep their meaning only for a demanded start that failed.
- **Hypotheses, free to change within these constraints.** The verb's name and frame; whether the 5-minute window is a constant beside `PACE` or an environment declaration; and how the agent service learns that cadrumo-agent is about to read a document. Candidates for the last are a service hook on the local-lane run start, or cadrumo-agent asking its host before `make_resident`.

Reconciliation, applied with this amendment:

1. `2026-10-04-runtime-manager-architecture-adr`, "The manager supervises the local AI server". Current: "it starts it while the local AI is set up, restarts it after a crash". Proposed: "it keeps the server dormant while the local AI is set up and starts it only when the agent service demands it through an admitted manager IPC verb, restarts it after a crash while it is demanded, stops it after 5 minutes holding no model".
2. `2026-10-24-rust-component-provisioning-adr` constraint 12. Current: "It starts only the selected engine's server: the packaged llama-server while `llamacpp` is selected and the package carries it, and the Ollama server while `ollama` is selected and its program is installed and verified." Proposed: "It runs only the selected engine's server, and only on demand: the packaged llama-server while `llamacpp` is selected and the package carries it, and the Ollama server while `ollama` is selected and its program is installed and verified, each started when the agent service demands it and stopped after 5 minutes holding no model (`2026-11-07-local-inference-engine-adr`, amendment 2026-11-11)." Its last sentence, "Where no manager runs (a development checkout), the local AI reads `program_not_running`", is unchanged.

Authorization: the coordinator approved this direction and its rulings on 2026-11-11: the IPC verb as the only channel, agent-service-only callers, dormant at start, 5-minute idle stop, no demand from status or setup, and re-scoping E13. The coordinator accepted this amendment as written at bcd69c19ba under delegated design authority on the same day. Both reconciliations above are applied in the same change.
