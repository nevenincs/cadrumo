---
tags:
  - '#research'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave5-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave5-adr]]"
---



# `secure-persistence-foundation` wave-6 research

## Question

Wave 5 closed the run-trace + submission engine carry-forwards. Wave 6
addresses the next class of consumer that today writes identity-bearing
data without the substrate's redaction gate: the **LLM cache and usage
log**. These are diagnostic-class artefacts that may carry full
financial classification prompts (transaction descriptions including
counterparty names, addresses, NIF strings) and the LLM's echoed
response text.

## Findings

### LLM cache writes raw response payloads

`LLMCache.write` calls `entry.model_dump_json(indent=2)` and writes
the result to a content-addressed JSON file under
``aeat_llm_cache_dir``. The cached entry contains the full LLM
response text — which may echo identity-bearing context from the
prompt (e.g. a transaction classification prompt
"classify: 'Transferencia a Juan García-Pérez NIF 12345678Z'" can
yield a response that echoes the NIF).

### LLM usage log writes prompt + response text

`UsageRecorder.record` appends one JSON-encoded `UsageRecord` per
line to a daily JSONL file under ``aeat_llm_usage_dir``. The record's
``text`` field is the full response text — same leakage surface as
the cache.

### Existing `aeat.adapters.persistence.storage` substrate covers the discipline

The substrate's `redact_structured(value, rules=
default_rules_for_class(SensitivityClass.CACHE))` walks the dumped
dict and applies the CACHE-class redaction rule set (NIF SHA-256-
prefixed, URL host-only, bearer-shape fingerprinted). The wave-5
observability sink and the wave-4 governed audit sink demonstrated
the same pattern at DIAGNOSTIC and AUDIT class respectively.

### Cache hit semantics

`LLMCache.read` returns the cached `LLMResponse` to the caller. If
the cache content has been redacted at write, the caller receives
the redacted text — which is what we want, because the caller would
otherwise re-feed the unredacted text into the next prompt
classification step. The redaction is applied *idempotently*: a
re-read of an already-redacted entry stays unchanged because the
redaction rules are stable functions of the input.

## Dependencies

- Substrate's `redact_structured` (wave-3 close + wave-5 phase 1
  pattern).
- `default_rules_for_class(SensitivityClass.CACHE)` and
  `default_rules_for_class(SensitivityClass.DIAGNOSTIC)`.

No new substrate work is needed; this is consumer-migration work
plus a redaction wrapper around two writers.

## Recommended scope

1. Wrap `LLMCache.write` so every response is redacted before
   persistence at CACHE class.
2. Wrap `UsageRecorder.record` so every usage record is redacted
   before persistence at DIAGNOSTIC class.
3. Tests that confirm the discipline: NIF canary in a synthetic
   response never lands in the on-disk JSON / JSONL.

## Out of scope

- Status cache redaction (deferred to Wave 7).
- Corpus integrity tracking (CORPUS class SHA-256 manifest — separate
  ADR after wave 7).
- Connector + export governance (Wave 7).
- Ciphertext-payload wiring for envelopes (separate ADR).
