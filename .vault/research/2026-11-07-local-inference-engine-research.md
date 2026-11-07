---
tags:
  - '#research'
  - '#local-inference-engine'
date: '2026-11-07'
modified: '2026-11-07'
body_schema: 'body-v2'
body_hash: 'sha256:46f26e9d67ed83381d491f204a8a3b70a7abd87cc9a2ce99a3dc036a575f43d5'
related: []
---

# `local-inference-engine` research: `Local inference engine comparison: Ollama, llama.cpp, vLLM`

The question is which local inference engines Cadrumo can run beside the Ollama program it already provisions, and what each costs in native provisioning and in cadrumo-agent. Ollama is coupled to a bounded set of native modules and to one agent lane. Most of the native provisioning machinery is engine-neutral. llama.cpp's `llama-server` is MIT-licensed, ships small per-backend archives, and serves an OpenAI-compatible API with router-mode residency. vLLM has no native Windows build and depends on Python and PyTorch, so it does not fit a desktop product with Rust-only provisioning. A CPU pass on 2026-11-07 showed that an Ollama text blob loads in llama-server in place, while Ollama's single-GGUF vision blob does not. A GPU pass is pending.

## Findings

### Native provisioning is coupled to Ollama in a bounded set of modules

- The program pin is Ollama v0.40.10 in `native/component-pins/local_ai_program.toml`: the win-x64 zip is 1,586,229,413 bytes, the linux-x64 tar.zst 1,509,264,197 bytes and the darwin tgz 181,123,017 bytes. `dev/env/local_ai_pins.py` generates the file.
- The engine verifies each archive's size and SHA-256 while it streams to disk (`native/application/src/component.rs:577-586`).
- The pin parser accepts one program identity only. It refuses `raw.program != "ollama"` (`native/application/src/provisioning/pins.rs:252`).
- Models are pulled from `registry.ollama.ai` through the managed server's `/api/pull` (`native/application/src/provisioning/local_ai/models.rs:529`, `:546`). `DEFAULT_REGISTRY` is at `models.rs:54`.
- `Program::start` spawns the server with the argument `serve`. It clears the environment and sets `OLLAMA_HOST`, `OLLAMA_MODELS` and `OLLAMA_HOME` (`native/application/src/provisioning/local_ai/program.rs:854`, `:882`, `:900-902`). Readiness is the `Listening on ` banner plus `/api/version` (`program.rs:85`, `:499-512`).
- `ServerSupervisor` restarts after 1 s, doubling the wait to at most 60 s. It fails at 5 restarts within 600 s (`native/application/src/provisioning/local_ai/supervision.rs:45-53`).
- The runtime manager's `LocalAiHost` contains the server in a Job Object (`native/manager/src/supervision/local_ai.rs:87`, `:108`, `:236-264`).
- The server address `127.0.0.1:23743` is declared once (`native/application-environment.toml:286`).
- Ollama-specific code: `models.rs` (740 lines), part of `program.rs` (1072 lines), `fake_ollama.rs` (347 lines), `models/tests.rs` (980 lines) and `engine/tests.rs` (1246 lines).
- Engine-neutral code: `Containment`, `ServerSupervisor`, `loopback.rs`, `ComponentStore` and `Artifact`, `lease.rs`, `plan.rs`, `items.rs` and `hardware.rs`.

### The agent service and cadrumo-agent are coupled to Ollama through one lane

- The agent service sets `CADRUMO_AGENT_OLLAMA_BASE_URL` to `http://127.0.0.1:23743` (`src/cadrumo_agent_service/host/launch_environment.py:70-72`, `:322`).
- cadrumo-agent's `ollama_api` lane uses Ollama's native `/api/chat` NDJSON stream (`cadrumo-agent:src/cadrumo_agent/providers/ollama_chat_model.py:385`, `:788-844`).
- Its admission loads a model at the requested `num_ctx` through `/api/generate` and checks residency through `/api/ps` (`cadrumo-agent:src/cadrumo_agent/providers/ollama_residency.py:162-269`). It detects out-of-memory by matching error text (`ollama_residency.py:68-81`).
- It probes capabilities through `/api/show` and `/api/tags` (`cadrumo-agent:src/cadrumo_agent/providers/ollama_probe.py:45-188`).
- The declared models are `qwen3:1.7b`, `qwen3:4b`, `qwen3-vl:2b`, `qwen3-vl:4b` and `qwen3-vl:4b-instruct` (`cadrumo-agent:src/cadrumo_agent/providers/provider_metadata.json:7593-7926`).
- The lane registry is at `cadrumo-agent:src/cadrumo_agent/providers/registry.py:49`, `:155`, `:206`. The lane factory is at `providers/_lane_models.py:483-522`.
- The live-proof gate binds `binary="ollama"` (`cadrumo-agent:src/cadrumo_agent/providers/lane_admission.py:330-341`).
- The declared catalogue is schema 5 (`cadrumo-agent:src/cadrumo_agent/providers/declared_catalog.py:103`).

### Cadrumo-side gates constrain any second engine

- Python never provisions a component (`dev/quality/tests/test_no_python_provisioning.py`).
- Cadrumo defines no model name or digest (`dev/quality/tests/test_no_model_definitions.py`).
- Tax extraction reaches a model only through `AgentAdapter` (`src/cadrumo/adapters/outbound/llm/providers/agent.py:108`).

### Ollama: current, large, with its own engine

- The latest release is v0.40.15, MIT-licensed. Its Windows zip is 1614.9 MB and includes NVIDIA libraries (https://github.com/ollama/ollama/releases).
- Since 0.7.1, Ollama runs multimodal models on its own Go/GGML engine rather than through llama.cpp's server (https://registry.ollama.ai/blog/multimodal-models). A model packaged for that engine is therefore not guaranteed to load in llama-server.

### llama.cpp: small per-backend archives and an OpenAI-compatible server

- llama.cpp is MIT-licensed. Releases carry `bNNNNN` build tags, plus v0.9.0 tags (https://github.com/ggml-org/llama.cpp/releases).
- Windows x64 archive sizes:
  - CPU: 24.7 MB.
  - Vulkan: 37.7 MB.
  - CUDA 12.4: 288.7 MB, plus cudart 391.4 MB.
  - CUDA 13.5: 170.8 MB, plus cudart 426.3 MB.
  - ROCm: 267.3 MB.
  - SYCL: 156.1 MB.
- Other platforms: macOS arm64 is 16.7 MB, Linux CPU 23.1 MB and Linux Vulkan 35.9 MB.
- `llama-server` serves OpenAI `/v1/chat/completions` (https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md). It supports `response_format` json_schema and grammar, tools through `--jinja`, and `/v1/embeddings`.
- Multimodal input goes through `--mmproj`, which the README marks experimental. `-hf` downloads a model from Hugging Face.
- `/health` answers 503 while a model loads and 200 when it is ready. `/props` reports `default_generation_settings.n_ctx`, `modalities`, `chat_template` and `build_info`.
- The default `-c 0` takes the context size from the model.
- Router mode starts without `-m` and serves `/models`, `/models/load` and `/models/unload` (https://huggingface.co/blog/ggml-org/model-management-in-llamacpp, 2025-12-11). Its flags:
  - `--models-max` caps residency. The default is 4, and the least recently used model unloads.
  - `--models-memory-margin` keeps device memory free.
  - `--no-models-autoload` disables autoload.
- Router models are discovered from `--models-dir`, or configured in a `--models-preset` INI file with one section per model and keys such as `model` and `ctx-size`.
- The sources read describe only a `model` field in the `/models/load` body. They do not document per-load arguments such as context size.
- Every README example uses a `.gguf` name. The CPU pass showed that llama-server also loads an extensionless Ollama blob named `sha256-<digest>` (Measurement evidence, CPU pass).

### vLLM: not a desktop engine

- The latest release is v0.33.0rc3, Apache-2.0. It has no native Windows build (https://docs.vllm.ai/en/latest/getting_started/installation/gpu/).
- It ships as Python and PyTorch wheels and preallocates VRAM through `gpu_memory_utilization` (https://docs.vllm.ai/en/latest/configuration/optimization/).
- It conflicts with Rust-only provisioning, with Windows support and with sharing a desktop GPU. The evidence favours rejecting it.

### What the decision must settle

- Engine selection: component state, or a cadrumo-agent lane.
- Pinning: llama.cpp's per-backend archives, against Ollama's single bundle.
- Model acquisition and integrity: Ollama's content-addressed store, a native registry client, or Hugging Face GGUF plus mmproj.
- Context size: Ollama takes `num_ctx` per request, while llama-server fixes it when a model loads.

Not investigated:

- GPU backends beyond the listed archives.
- The licence terms of individual GGUF repositories.
- llama.cpp's macOS code-signing state.

## Measurement evidence (CPU pass, 2026-11-07)

The pass ran Ollama 0.40.13 and llama-server b12184 (Windows CPU build) side by side on one Windows host. Both ran CPU-only, with 8 threads and a 4096-token context. Requests alternated between the engines, and each figure is the median of 3 repetitions. All documents were synthetic.

The host was contended: a concurrent vaultspec-rag index rebuild ran throughout, at 34-99% host CPU. The performance figures therefore compare the two engines relative to each other only. They are not absolute throughput.

### Archive size

| Asset (b12184 unless named) | Zipped bytes | Unzipped bytes |
|---|---|---|
| `llama-b12184-bin-win-cpu-x64.zip` | 24,749,741 | 63,767,837 |
| `llama-b12184-bin-win-vulkan-x64.zip` | 37,709,845 | 105,770,269 |
| `llama-b12184-bin-win-cuda-12.4-x64.zip` | 288,724,926 | 677,717,789 |
| `cudart-llama-bin-win-cuda-12.4-x64.zip` | 391,443,627 | 574,138,880 |
| `llama-b12184-bin-win-cuda-13.5-x64.zip` | 170,769,237 | 224,471,837 |
| `cudart-llama-bin-win-cuda-13.5-x64.zip` | 426,314,199 | 554,866,512 |
| `ollama-windows-amd64.zip` (pinned v0.40.10) | 1,586,229,413 | 2,230,768,655 |
| `ollama-windows-amd64.zip` (newer release) | 1,601,969,847 | 2,249,796,111 |

### Model storage

These are the layer sizes from the registry manifests the pass fetched.

| Tag | Model layer bytes | Projector layer bytes | Other layers |
|---|---|---|---|
| `qwen3:1.7b` | 1,359,279,776 | none | template, licence, params |
| `qwen3:4b` | 2,497,280,480 | none | template, licence, params |
| `qwen3-vl:2b` | 1,889,496,384 | none (single GGUF) | licence, params |
| `qwen3-vl:4b-instruct` | 2,497,888,288 | 839,325,760 (`application/vnd.ollama.image.projector`) | licence, params |

The Hugging Face vision pair was `Qwen3VL-2B-Instruct-Q4_K_M.gguf` plus `mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf`. The pass did not keep the sizes of those files.

### Performance (relative only, contended host)

| Engine | Model | Cold load s | TTFT s | Prompt tok/s | Gen tok/s | Peak RSS tree MB |
|---|---|---|---|---|---|---|
| Ollama | `qwen3:1.7b` | 3.179 | 0.274 | 181.19 | 12.54 | 1865 |
| llama-server | `qwen3:1.7b`, same Ollama blob | 2.688 | 0.251 | 150.09 | 12.96 | 2283 |
| Ollama | `qwen3-vl:2b` | 3.347 | 0.242 | 152.42 | 18.04 | 2624 |
| llama-server | Qwen3-VL-2B-Instruct Q4_K_M + mmproj Q8_0 (HF) | 2.736 | 0.156 | 195.64 | 15.23 | 2658 |

TTFT is the time to the first streamed token.

### Extraction quality

Each engine extracted eight fields from five synthetic Spanish invoices and receipts under a JSON schema, with up to 2048 output tokens. Text runs read the document text. Vision runs read a PNG.

| Engine | Model | Input | Schema-valid | Field accuracy | Misses |
|---|---|---|---|---|---|
| Ollama | `qwen3:1.7b` | text | 1.0 | 0.875 | one each of issuer_name, date, base, iva_amount, total |
| llama-server | `qwen3:1.7b`, same Ollama blob | text | 1.0 | 0.925 | one each of base, iva_amount, total |
| Ollama | `qwen3-vl:2b` | png | 0.4 | 0.375 | three empty replies; one base wrong |
| llama-server | Qwen3-VL-2B-Instruct Q4_K_M + mmproj Q8_0 (HF) | png | 1.0 | 0.95 | two dates in DD/MM/YYYY form |

The Ollama `qwen3-vl:2b` row is a lane defect, not a model ceiling. Three of the five requests returned empty content after 170-217 s. The two valid replies took 131 s and 57 s. The defect and its repro are in `2026-11-07-local-inference-engine-audit`.

### Blob compatibility with llama-server b12184

- `qwen3:1.7b` loads. llama-server reads the extensionless blob `blobs/sha256-3d0b7905...` in place through `-m`, so a `.gguf` name is not required.
- `qwen3-vl:2b` is refused with `error loading model hyperparameters: key not found in model: qwen3vl.rope.dimension_sections`. The tag is Ollama's single-GGUF vision format. Ollama 0.40.13's own server log shows it translating that blob internally ("detected Ollama-format qwen3vl GGUF used as mmproj; translating", projector type `qwen3vl_merger`). Upstream llama-server has no such translation.
- `qwen3-vl:4b-instruct` ships a separate projector layer. Loading it in llama-server is deferred to the GPU pass.

### Context and router probes

- Started with no `-c`, llama-server sized `qwen3:1.7b` at `n_ctx` 40960 over 4 slots, which is the model's full training context.
- In router mode with a `--models-preset` entry carrying `ctx-size = 4096` and `n-gpu-layers = 0`, `/models/load` succeeded in 3.51 s. The loaded model reported `n_ctx` 4096. A chat turn answered, and `/models/unload` succeeded.

### Harness

The harness scripts are `bench.py`, `interleave.py`, `extra_probes.py` and `probe_ollama_vl.py`, in the pass's temporary workspace. That workspace is not retained. This section is the durable record.

## Measurement evidence (GPU pass, pending)

An RTX 4080 SUPER pass follows, once it is coordinated with the desktop build. It settles the default vision route (registry projector layer or Hugging Face GGUF plus mmproj), measures `auto` placement on Vulkan, and repeats the performance tables on an uncontended host.

## Sources

- `native/component-pins/local_ai_program.toml`
- `dev/env/local_ai_pins.py`
- `native/application/src/component.rs:577-586`
- `native/application/src/provisioning/pins.rs:252`
- `native/application/src/provisioning/local_ai/models.rs:54`, `:529`, `:546`
- `native/application/src/provisioning/local_ai/program.rs:85`, `:499-512`, `:854`, `:882`, `:900-902`
- `native/application/src/provisioning/local_ai/supervision.rs:45-53`
- `native/manager/src/supervision/local_ai.rs:87`, `:108`, `:236-264`
- `native/application-environment.toml:286`
- `src/cadrumo_agent_service/host/launch_environment.py:70-72`, `:322`
- `cadrumo-agent:src/cadrumo_agent/providers/ollama_chat_model.py:385`, `:788-844`
- `cadrumo-agent:src/cadrumo_agent/providers/ollama_residency.py:68-81`, `:162-269`
- `cadrumo-agent:src/cadrumo_agent/providers/ollama_probe.py:45-188`
- `cadrumo-agent:src/cadrumo_agent/providers/provider_metadata.json:7593-7926`
- `cadrumo-agent:src/cadrumo_agent/providers/registry.py:49`, `:155`, `:206`
- `cadrumo-agent:src/cadrumo_agent/providers/_lane_models.py:483-522`
- `cadrumo-agent:src/cadrumo_agent/providers/lane_admission.py:330-341`
- `cadrumo-agent:src/cadrumo_agent/providers/declared_catalog.py:103`
- `dev/quality/tests/test_no_python_provisioning.py`
- `dev/quality/tests/test_no_model_definitions.py`
- `src/cadrumo/adapters/outbound/llm/providers/agent.py:108`
- https://github.com/ollama/ollama/releases
- https://registry.ollama.ai/blog/multimodal-models
- https://github.com/ggml-org/llama.cpp/releases
- https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md
- https://huggingface.co/blog/ggml-org/model-management-in-llamacpp
- https://docs.vllm.ai/en/latest/getting_started/installation/gpu/
- https://docs.vllm.ai/en/latest/configuration/optimization/
- CPU measurement pass, 2026-11-07: harness `bench.py`, `interleave.py`, `extra_probes.py` and `probe_ollama_vl.py`, with results in `results.md` and `results.json`, in a temporary workspace that is not retained.
- Verification status: the external release versions and archive sizes are as supplied on 2026-11-07 and were not re-downloaded. The README and router facts were read on 2026-11-07. These locators were spot-checked: `pins.rs:252`, `supervision.rs:45-53`, `launch_environment.py:70-72`, `ollama_residency.py:68-81`, `declared_catalog.py:103` and `lane_admission.py:330-341`.
