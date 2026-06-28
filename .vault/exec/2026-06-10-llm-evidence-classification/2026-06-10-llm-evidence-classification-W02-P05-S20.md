---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S20'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Add an on-host vision read test (PDF rasterise plus local in-memory images path)

## Scope

- `src/aeat/adapters/outbound/llm/tests/test_local_vision.py`

## Description

- Add `test_local_vision.py` under `adapters/outbound/llm/tests/`.
- Build a one-page text-layer-free raster PDF in memory (Pillow `save(format="PDF")`); rasterise it and assert one base64 PNG page is returned with a valid PNG magic header.
- Stand up a loopback Ollama-shaped `ThreadingHTTPServer`, point `aeat_llm_ollama_chat_url` at it via `override_settings`, run `LocalAdapter.complete` with the rasterised images, and assert the server received them on `messages[-1].images` and the completion parsed.

## Outcome

- Proves the on-host vision read: a scan-only PDF is rasterised in process memory and the base64 images reach the adapter's HTTP body with no byte leaving the host (endpoint bound to `127.0.0.1`). Both cases pass; real local HTTP server, no mocks.

## Notes

- The JSON request body is narrowed with `isinstance` plus scoped `# ty: ignore` comments, mirroring the sibling `test_gemini.py` pattern for the `json.loads` boundary.
