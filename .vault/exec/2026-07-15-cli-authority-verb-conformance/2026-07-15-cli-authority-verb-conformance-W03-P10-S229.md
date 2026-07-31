---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:1ae506ab1ba09d6f0d04770400b5116af14e3bc2385b411d5498045503d406bc'
step_id: 'S229'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Delegate perception, retention, and calculation observation object-key digests to core sha256_hex while preserving the exact normalized key bytes

## Scope

- `src/cadrumo/application/aggregation/_percepciones_observations_repository.py`
- `src/cadrumo/application/aggregation/_retencion_observations_repository.py`
- `src/cadrumo/application/calculations/_observations_repository.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `604c8dce53` routed sixteen production one-shot SHA-256 bodies through `core.hashing.sha256_hex`, including these three repositories.

- Route the percepciones observation object key through `core.hashing.sha256_hex`, preserving the exact normalized token bytes.
- Route the retencion observation object key through `core.hashing.sha256_hex`, preserving the exact normalized token bytes.
- Route the calculation observation repository's decision digest and two further object-key digests through `core.hashing.sha256_hex`, preserving the exact `\x1f`-joined normalized key bytes.

## Outcome

`src/cadrumo/application/aggregation/_percepciones_observations_repository.py` imports `sha256_hex` from `...core.hashing` at line 62 and calls it at line 97 over a UTF-8-encoded token. `_retencion_observations_repository.py` imports `sha256_hex` at line 48 and calls it at line 83, same shape. `src/cadrumo/application/calculations/_observations_repository.py` imports `sha256_hex` at line 55 and calls it three times: line 130 over `decision.model_dump_json()`, and lines 214 and 225 over the normalized object-key bytes.

Verified against HEAD: all three modules' import and call sites match the audit brief exactly; these are persisted object-key digests, so a drift here would silently orphan stored observation records — the delegation being behaviour-preserving by construction (identical argument expressions) is the load-bearing guarantee.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/application/aggregation/tests/test_percepciones_observations_repository_roundtrip.py src/cadrumo/application/aggregation/tests/test_retencion_observations_repository_roundtrip.py src/cadrumo/application/calculations/tests/test_observations_repository.py src/cadrumo/application/calculations/tests/test_observations_repository_roundtrip.py` reports 43 passed.

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work. The roundtrip suites exercise the real encrypted secure-object repository, not a test double, so a key-derivation drift would surface as a real lookup miss rather than a mocked pass.
