---
tags:
  - '#adr'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - "[[2026-06-13-llm-evidence-classification-research]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
---



# `llm-evidence-classification` adr: `Default local vision model bound to consumer-grade hardware` | (**status:** `accepted`)

## Problem Statement

The on-host vision evidence reader defaults to a local Ollama vision model named
by `aeat_llm_ollama_vision_model`. The initial default `llama3.2-vision` (11B)
needs roughly 8-16 GB of VRAM, so on a normal consumer-grade machine (a typical
laptop or desktop with a modest or integrated GPU, or CPU-only) it either fails
to load or runs unusably slowly. The on-host posture is the gestor-allowed,
no-upload default, so the default model must actually run on the hardware a
gestor or autónomo is likely to have, not just on a workstation GPU.

## Considerations

Reading invoices is structured-document OCR, where the Qwen2.5-VL family leads
small models. The model only selects `category` / `iva_category` from the
registry allow-list; it never emits a regulated number (those are
registry-derived), so a strong-OCR small model suffices. Footprint, OCR quality,
and Ollama availability were weighed across `qwen2.5vl:7b` (~6 GB),
`qwen2.5vl:3b` (~3 GB), `moondream` (~1.7 GB), `minicpm-v` (8B), and the incumbent
`llama3.2-vision` (11B). Weights are pulled by the operator into their own Ollama
runtime; the application ships none.

## Constraints

The vision read requires a running local Ollama with the named model pulled; when
it is absent the read fails and the operator must `ollama pull` the model (an
operator prerequisite, documented). The model name is a settings default, not a
hard dependency: an operator selects a heavier or lighter model per their
hardware by overriding `aeat_llm_ollama_vision_model`. The choice depends only on
the stable `LocalVisionLLMClassifier` / `LocalAdapter` Ollama path already
shipped; no frontier dependency.

## Implementation

Change the central default `aeat_llm_ollama_vision_model` from `llama3.2-vision`
to `qwen2.5vl:3b`. Document the tiering for operators: `qwen2.5vl:3b` is the
consumer-hardware default (modest GPU or CPU, ~3 GB); `qwen2.5vl:7b` is the
quality upgrade for an 8 GB+ GPU; `moondream` is the CPU-only / very-low-memory
fallback. All are pulled on demand from Ollama; the application reads the name
from settings at the boundary and passes it as the request `model_override`.

## Rationale

Grounded in the sibling research: Qwen2.5-VL is best-in-class small document/OCR,
and its 3B variant is the recommended VLM for modest/edge devices while staying
document-grade for invoices. It is the balance point between "reads invoices
well" and "runs on normal consumer hardware". Heavier (`7b`, `minicpm-v`) and
lighter (`moondream`) options remain one settings override away, so no operator
is locked out by the default.

## Consequences

A gestor or autónomo on ordinary hardware can now actually run the on-host vision
read, fulfilling the ADR posture that scanned/image evidence is read locally with
no upload. The default is smaller and faster than the incumbent and better at
documents for its size. Honest limitations: the 3B model's OCR is slightly weaker
than the 7B on dense multi-line invoices (operators with a GPU should override to
`7b`); the operator must pull the model once (~3 GB); and a CPU-only run is slower
than a GPU run though still usable with the 3B / moondream tier. The model name
is a regulatory-neutral runtime knob (it never produces a persisted tax number),
so changing the default carries no calculation-grounding risk.

## Codification candidates


