---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:e970127e7c96127d55d83cd2c517126f9a8a428ddad85b6985156bb2629fa545'
step_id: 'S10'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Add retention-days pruning to the LLM response cache and usage JSONL following the run-telemetry precedent

## Scope

- `src/cadrumo/adapters/outbound/llm`

## Description

- Add four Settings fields mirroring the run-telemetry retention pair: `cadrumo_llm_cache_retention_days` / `cadrumo_llm_cache_max_records` and `cadrumo_llm_usage_retention_days` / `cadrumo_llm_usage_max_records`, all defaulting to 30 days / 5000 records.
- Reshape `LLMCache.prune()` (a former full-partition clear with no callers) into the two-stage `prune(retention_days, max_records)` shape: remove entries older than the cutoff, then evict the oldest excess beyond the cap, defaulting to the central settings.
- Add the same two-stage `prune` to `UsageRecorder`, and make `record()` persist its `object_key_uuid` in the payload (mirroring telemetry) so `prune` can reconstruct each save-time key; add `_load_records_with_object_keys` and route `load_records` through it.
- Add real-behavior retention tests for both families (age cutoff, both-bounds-kept, count-cap-evicts-oldest, settings default), plus the env template entries and a regenerated env-overrides reference.

## Outcome

The LLM response cache and usage store now carry a declared retention lifecycle instead of unbounded growth, uniform with run-telemetry. Gates: the full LLM adapter suite is 58 passed (1 deselected live test), the new retention suites are 7 passed under sequential (`-n 0`), the settings/env-parity and env-reference freshness gates pass, collection is clean repo-wide, and ruff is clean.

## Notes

Both stores persist in the encrypted per-bucket secure-object backend (not on-disk files); the dir settings are logical partition roots, so "retention" prunes records, not files. The cache natural key is deterministic (provider/model/prompt/args hashes) so its prune reconstructs keys directly; the usage key embedded a random uuid, so - as telemetry already does - the uuid is now persisted in the payload to make the save-time key reconstructable. Age control in the tests uses an explicit past `created_at` written through the real save path rather than a frozen clock, because freezing to an instant unrelated to the real session deadline expires the active bucket session (the run-telemetry retention test documents the same constraint).
