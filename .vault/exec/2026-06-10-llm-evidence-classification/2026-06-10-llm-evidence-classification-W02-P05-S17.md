---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S17'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Extend the LocalAdapter with the Ollama images field and add on-host PDF rasterisation for a local vision model

## Scope

- `src/aeat/adapters/outbound/llm/_providers/local.py`

## Description

- Add an `images` base64 field to the normalized `ProviderRequest` in `base.py` (default empty; transient, in-memory, never persisted).
- Forward `request.images` on the Ollama `messages[].images` field in `LocalAdapter.complete`, present only when a vision read supplied them so text-only requests stay byte-identical.
- Resolve the Ollama chat URL per call via `load_settings().aeat_llm_ollama_chat_url` (replacing the import-time module constant) so the endpoint is overridable at the settings boundary.
- Add `rasterise_pdf_pages_to_base64_png` to `local.py`: render each page of an in-memory PDF to a base64 PNG via pypdfium2 + Pillow, fully on-host, no temp file.

## Outcome

- `LocalAdapter` now carries a multimodal vision path: a scan-only PDF is rasterised in process memory and forwarded to a localhost Ollama vision model. Verified by `test_local_vision.py` and the full `adapters/outbound/llm` suite (54 passed); ruff and ty clean.

## Notes

- pypdfium2's iterated page type omits `render` in its bundled stub (third-party boundary); annotated with a single scoped `# ty: ignore[unresolved-attribute]`. The generic LLM-client path is not yet wired into the subprocess classify flow that ships today; this is the on-host vision-reader infrastructure the plan scoped for W02.P05.
