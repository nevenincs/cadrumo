---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:f7360d649fbdd3ea1a073d91199632cbbdf3119eccfaa76553a5a4ecaa14234e'
step_id: 'S32'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Wire the dormant LLM and run-trace retention prunes into production paths, narrow the usage read-path uuid refusal, and add the retention-wiring gate (W02 review remediation)

## Scope

- `src/cadrumo/adapters/outbound/llm/_client.py`

## Description

- HIGH: the LLM cache / usage / run-telemetry and run-trace retention prunes had no production caller (R3's bounded-growth promise was unmet in practice). Wire them:
  - Add a best-effort `LLMClient._sweep_retention_stores()` invoked from `LLMClient.__init__`, pruning the cache, usage, and run-telemetry recorders once per client construction (not per append, which would rescan the whole encrypted store on every call).
  - Prune run-trace directories from `save_trace` at run finalisation.
- Add `test_retention_wiring_gate.py`: for every RETENTION-classified family, assert a production prune call site exists in the owning module (grep-based), so a family whose prune goes dormant fails CI.
- Add per-family real-behavior tests that the wiring FIRES: constructing an `LLMClient` around a recorder prunes its pre-seeded stale records; saving a trace prunes a pre-existing stale run directory.
- MEDIUM: decouple the usage read path from key reconstruction - `load_records` iterates records directly, so a legacy record lacking `object_key_uuid` stays readable; `_load_records_with_object_keys` (prune-only) yields a `None` key and logs, and `prune` hard-refuses when any key is unreconstructable. Tests cover both the tolerant read and the hard prune refusal.
- LOW: the wiring gate also asserts the registry disk-cache accessor holds no `PROJECT_ROOT` literal, closing the opt-in-field escape from the lifecycle gate's derivation check.

## Outcome

Every retention family now prunes from a real production path, verified both by the grep wiring gate and by behavioral "wiring fires" tests. The usage view no longer bricks on pre-change records while prune still surfaces uuid corruption loudly. Gates: the full LLM adapter suite, the run-trace retention suite, the lifecycle gate, and the new wiring gate are 80 passed under sequential (`-n 0`); ruff clean; collection clean repo-wide.

## Notes

Chosen trigger design: the per-append prune attempted first was reverted because it deleted records with an old `created_at` at write time - regressing the fixed-date storage-roundtrip/summary suites and drifting over real time - and because pruning an append-only audit store on every append rescans the whole encrypted store. The once-per-client sweep (and once-per-run save_trace prune) fires on real production paths without touching the direct-recorder write path the roundtrip tests exercise. The `LLMClient` sweep is layering-clean (same adapter layer owns the three stores); run-trace pruning stays inside core observability. Only the usage store needed the read-path narrowing because only its uuid field is new (added this campaign); run-telemetry always wrote its uuid, so its load-path hard-raise stays as an intentional anti-tautology corruption guard.
