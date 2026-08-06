---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:8757beca35a2f518fb43fcdb7cb58c815257b8105fd5b6f00ab59f898ed1d642'
step_id: 'S227'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Delegate Clave Movil, outbound LLM cache, and agent evaluation one-shot fingerprints to core sha256_hex while preserving truncation and exact encoded inputs

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_support.py`
- `src/cadrumo/adapters/outbound/llm/_cache.py`
- `src/cadrumo/agent/eval/_flywheel.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `604c8dce53` routed sixteen production one-shot SHA-256 bodies through `core.hashing.sha256_hex`, including these three modules.

- Route the Clave Movil diagnostics fingerprint through `core.hashing.sha256_hex`, preserving the truncation applied at the call site.
- Route the outbound LLM cache key components through `core.hashing.sha256_hex`, preserving the exact encoded prompt/argument inputs.
- Route the agent-eval flywheel fingerprint through `core.hashing.sha256_hex`, preserving its truncation.

## Outcome

`src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_support.py` imports `sha256_hex` from `.....core.hashing` at line 19 and calls it at line 200, truncating the result to 12 characters at the call site (`[:12]`), unchanged. `src/cadrumo/adapters/outbound/llm/_cache.py` imports `sha256_hex` from `....core.hashing` at line 23 and calls it twice at lines 109-110 for the prompt hash and args hash, both over UTF-8-encoded text. `src/cadrumo/agent/eval/_flywheel.py` imports `sha256_hex` from `...core.hashing` at line 19 and calls it at line 36, truncating to 12 characters, unchanged.

Verified against HEAD: all three modules' import and call sites match the audit brief exactly and preserve their respective truncations and encodings.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_movil.py src/cadrumo/adapters/outbound/llm/tests/test_cache.py src/cadrumo/adapters/outbound/llm/tests/test_cache_retention.py src/cadrumo/adapters/outbound/llm/tests/test_cache_roundtrip.py src/cadrumo/agent/eval/tests/test_report_and_flywheel.py` reports 38 passed.

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work.
