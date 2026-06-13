---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S19'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Add a cache-key collision test proving two evidence docs under the same prompt yield distinct keys

## Scope

- `src/aeat/adapters/outbound/llm/tests/test_cache.py`

## Description

- Add `test_cache_key_distinguishes_multimodal_evidence` to `test_cache.py`: build keys for a text-only request and for two requests carrying evidence with different content addresses.
- Assert the three `args_hash` values are distinct, and that the same content address with a different base64 payload reproduces the same key.

## Outcome

- Proves the S18 collision guarantee: distinct evidence documents under one prompt cannot share a cache entry, and the key folds the content address rather than the bytes. Passes (23 cache-suite tests green).

## Notes

- Real-behaviour test over the actual `build_key`; no mocks, no tautology.
