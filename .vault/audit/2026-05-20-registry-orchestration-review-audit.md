---
tags:
  - '#audit'
  - '#registry-orchestration'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-research]]'
---

# `registry-orchestration` Code Review

REGISTRY-ORCH-001 | HIGH | `ValidatedRegistryAuthority.load` cache can serve stale registry data after TOML changes
`ValidatedRegistryAuthority.load` delegates to `_load_authority`, but `_load_authority` is cached only by `root` and `source_root`. That means higher-level callers that correctly compute a registry tree fingerprint can still receive an old authority object. The concrete example is `build_runtime_schema_provider`: it includes `_registry_tree_fingerprint(root)` in its own cache key, but the cache miss then calls `ValidatedRegistryAuthority.load(root, source_root=...)`, which can return the stale `_load_authority` entry for the same path. This defeats the fragment architecture's fingerprint guarantee for long-lived processes, tests with mutable temp registries, and any operator-supplied registry root. The authority cache key should include the registry tree fingerprint, or the authority should not be path-cached independently of `load_registry_tree`.

Status 2026-05-20: resolved in the rollout. The authority cache key now receives the recursive registry TOML fingerprint, and `test_authority_cache_invalidates_when_fragmented_revision_changes` covers a mutable fragmented revision.

REGISTRY-ORCH-002 | MEDIUM | Same-record export fragment merge can silently preserve duplicate export field IDs
The same-id record merge appends `fields` arrays without checking nested field identity. The validator then builds `export_field_ids` with a set comprehension, so duplicate field IDs collapse rather than fail. A minimal two-fragment temp registry with both fragments declaring record `record` and field `field-1` loads as one record with two fields both named `field-1`. This makes `casilla.export_refs` ambiguous and lets accidental copy/paste duplication survive the split compiler. Add a nested duplicate-id check for `ExportRecordDefinition.fields` or validate duplicate export field IDs in `RegistryValidator`.

Status 2026-05-20: resolved for cross-fragment same-record appends. The loader now rejects duplicate appended table ids during directory-mode merges, with coverage in `test_directory_mode_rejects_duplicate_export_field_ids_after_record_merge`.

REGISTRY-ORCH-003 | LOW | Package-wide registry lint gate is currently blocked by unrelated import-order failures
`uv run ruff check src/aeat/domain/calculations/registry` reports 23 fixable issues, mostly import sorting in registry test modules plus one unused import in `test_constraints_text_shape.py`. This does not appear caused by the fragment loader hardening, but it prevents using the registry package ruff gate as a clean signal for this framework. Either fix those imports in a separate hygiene change or scope the gate to touched files until the package is clean.

Status 2026-05-21: now tracked explicitly in the rollout plan under `W05`. The package-wide registry ruff residual was fixed and closed as `W05.P09.S21`. The registry pytest package surface was verified through chunked diagnostics and closed as `W05.P09.S22`. M200 fragment-size hardening was verified and closed as `W05.P10.S23` through `W05.P10.S25`. Vault-wide pre-existing hygiene was separated from this rollout and closed as `W05.P11.S26`; `vault check all` still fails on broad pre-existing vault filename, index, and unrelated ADR-reference issues.

Performance note 2026-05-21: registry test runtime is suspicious and must not be treated as normal. Collection is cheap: `uv run pytest src/aeat/domain/calculations/registry --collect-only -q` collected 1,801 tests in 1.16s. Direct timing isolated repeated registry fingerprint and load work as the hot path, while Modelo 303 snapshot construction averaged about 0.081s. Test helper caches reduced repeated committed-registry loads and let the sorted package chunks pass, but ordinary registry subsets still took multiple minutes before cleanup: files 0..24 took about 286 seconds for 345 tests, files 25..49 took about 180 seconds for 487 tests, and files 85..89 took about 363 seconds for 168 tests. The rollout plan closed profiling, redundant-load reduction, budget establishment, and the remaining slow-chunk reduction as `W05.P12.S27` through `W05.P12.S30`; files 85..89 now pass in about 130 seconds.
