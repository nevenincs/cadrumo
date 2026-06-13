---
tags:
  - '#research'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-06-13'
related: []
---



# `llm-evidence-classification` research: `Local vision model for consumer-grade on-host evidence reading`

The on-host vision evidence reader (`LocalVisionLLMClassifier`) reads scanned and
image invoices with a local Ollama vision model. The default was
`llama3.2-vision` (11B), which needs roughly 8-16 GB of VRAM to run comfortably --
beyond "normal consumer-grade hardware" (a typical laptop or desktop with a
modest or integrated GPU, or CPU-only). This research evaluates smaller
multimodal models that read invoices well enough yet run on consumer hardware, to
ground the default-model decision.

## Findings

### The task is document OCR, not natural-image description

Invoice reading is structured-document understanding: extract supplier, line
items, amounts, and the IVA situation from a scanned page. Models tuned for
document/OCR (the Qwen2.5-VL family, MiniCPM-V, moondream's OCR mode) beat
LLaVA-style natural-image describers at the same parameter count. The model never
emits a regulated number (the registry derives those); it only reads the page to
select `category` / `iva_category` from the allow-list, so a strong-OCR small
model is sufficient.

### Candidate models and hardware footprint

- **Qwen2.5-VL 7B** (~6 GB): best-in-class small document/OCR model; 125K context.
  Comfortable on an 8 GB+ GPU. The quality tier for operators with a real GPU.
- **Qwen2.5-VL 3B** (~3 GB): nearly as capable on documents, faster, runs on
  modest/edge hardware (it is the recommended VLM for devices like a Jetson Orin
  Nano) and on CPU. Slightly weaker OCR than 7B but still document-grade. The best
  fit for "normal consumer hardware".
- **moondream2** (1.8B, ~1.7 GB): the only practical choice for CPU-only or
  speed-critical setups; supports structured (JSON) output and has improved OCR,
  but is weaker than Qwen2.5-VL on complex multi-line invoices. The ultra-low-end
  fallback.
- **MiniCPM-V 2.6** (8B): top-tier OCR on benchmarks but a larger footprint and a
  reported higher hallucination/error rate in at least one comparison.
- **llama3.2-vision 11B** (current default, ~8 GB): needs 8-16 GB VRAM; a
  natural-image model not specialised for documents. Too heavy and not the best
  OCR for its size -- the wrong default for consumer hardware.

### Hardware tiering

Single-GPU 8-16 GB → 7B comfortably; modest GPU / 8 GB shared / CPU → 3B; CPU-only
or very low memory → moondream. All three are available on Ollama
(`qwen2.5vl:7b`, `qwen2.5vl:3b`, `moondream`) and are pulled on demand, so the
choice is a settings default an operator can override per their hardware.

### Privacy and licensing are already satisfied by "local"

Running the model locally via Ollama keeps decrypted evidence bytes on-host (the
secure-storage invariant); no off-host upload, no consent gate, gestor-allowed.
Model weights are pulled by the operator into their own Ollama runtime; the
application ships no weights, so there is no model-licence shipping concern.

## Decision input

For a default that reads invoices well **and** runs on normal consumer-grade
hardware, `qwen2.5vl:3b` is the right balance: document/OCR-grade quality at a
~3 GB footprint that runs on a modest GPU or CPU. `qwen2.5vl:7b` is the
documented upgrade for an 8 GB+ GPU and `moondream` the CPU-only fallback; both
are reachable by overriding the model setting. The decision is ratified in the
sibling ADR.

## Sources

- Ollama Qwen2.5-VL model card (`ollama.com/library/qwen2.5vl`): 3B/7B/72B
  variants, sizes, context window.
- Roboflow "Best Local Vision-Language Models for Offline AI" and Trelis "top
  vision models 2025": Qwen2.5-VL document/OCR superiority over LLaVA at equal
  size; moondream as the CPU-only choice.
- NVIDIA-AI-IOT live-vlm-webui VLM list and LocalLLM Ollama VRAM guide:
  per-tier hardware recommendations (8-16 GB → 11B; edge/modest → 3B/moondream).
