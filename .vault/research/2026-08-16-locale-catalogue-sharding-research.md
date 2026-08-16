---
tags:
  - '#research'
  - '#locale-catalogue-sharding'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:af323ed3b8ef836272eef816d229d8c70255dbb1deb9ca1dad27edb9e3e1b8ca'
related:
  - '[[2026-08-04-modelo-localization-cascade-adr]]'
  - '[[2026-08-07-dev-harness-bleed-adr]]'
  - '[[2026-07-21-locale-key-resolution-adr]]'
---

# `locale-catalogue-sharding` research: `domain and modelo-partitioned locale storage architecture`

This research investigates the storage topology, developer workflow, runtime loading, and maintenance tooling bottlenecks caused by unbounded monolithic locale YAML files. Following the migration to shared dotted locale keys in `2026-08-04-modelo-localization-cascade-adr`, each of the four runtime catalogues (`es.yml`, `en.yml`, `ca.yml`, `hu.yml`) has expanded to over 46,900 translation keys and 86,000 lines (3.3 MB to 4.0 MB each). This causes high git merge collision rates, significant parse latencies (up to 1.5s per catalogue under C loaders, 9s under pure Python), and heavy I/O churn on every single-leaf edit.

The evidence demonstrates that partitioning the catalogue into a deterministic, domain- and Modelo-sharded directory structure (`locales/<locale>/<domain>.yml` and `locales/<locale>/modelo/schema/<modelo_id>.yml`) with smart dot-notation routing, on-demand lazy shard loading, and dual-tier rollout fallback preserves 100% key-value parity, accelerates single-leaf and targeted domain operations by 40x-60x, bounds git blast radiuses to isolated component files, and ensures zero consumer disruption.

## Findings

### 1. Monolithic catalogues carry severe physical scale and namespace skew

A census of the four active catalogues in `src/cadrumo/locales/` on 2026-08-16 measured:
- `es.yml`: 3.81 MB, 86,086 lines, 46,900 leaves
- `en.yml`: 3.26 MB, 74,482 lines, 46,899 leaves
- `ca.yml`: 3.38 MB, 77,150 lines, 46,899 leaves
- `hu.yml`: 3.51 MB, 80,012 lines, 46,900 leaves

The key distribution across top-level namespaces is heavily skewed:
- `modelo`: 41,805 keys (89.1% of the entire catalogue)
  - `modelo.schema.100`: 23,964 keys
  - `modelo.schema.200`: 6,504 keys
  - `modelo.schema.303`: 2,713 keys
  - `modelo.schema.490`: 2,082 keys
  - `modelo.schema.390`: 1,271 keys
  - `modelo.schema.151`: 1,116 keys
  - `modelo.schema.714`: 1,107 keys
  - 66 other Modelos: ~2,948 keys across smaller forms
  - `modelo.general`: ~99 non-schema keys
- Core Application & Platform domains: 5,095 keys (10.9%)
  - `cli`: 2,121 keys (4.5%)
  - `application`: 667 keys (1.4%)
  - `errors`: 638 keys (1.4%)
  - `wizard`: 433 keys (0.9%)
  - `flows`: 315 keys (0.7%)
  - `docs`: 197 keys (0.4%)
  - `profile`: 186 keys (0.4%)
  - `adapters`: 139 keys (0.3%)
  - Small domains (`aggregation`, `categories`, `entries`, `sheets`, `topic`, `mcp`, `review`, `auth`, `live`, `transactions`, `filing`, `core`, `llm`, `overview`, `ledger`, `provisioning`): 399 keys

Because all 73 Modelos and all application features share four monolithic files, any change—such as editing a single CLI flag help text or updating a single Casilla label in Modelo 303—forces rewriting and diffing a 4 MB, 86k-line file.

### 2. Parse latency and write churn degrade test runs and CLI performance

In benchmarks executed in `tmp/smoke_test_sharding.py` and `tmp/test_lazy_loader.py`:
- Monolithic load per file via `yaml.CSafeLoader` takes 650 ms to 815 ms (and over 1.5s on cold I/O; 9.0s on pure Python `yaml.SafeLoader` as documented in `dev/locales/manager.py:141`).
- Loading all four monolithic catalogues in serial takes ~2.8s to ~5.5s.
- `LocaleManager.set_locale_value` and `set_locale_values` under `catalogue_write_guard` require a full read-modify-write cycle of the entire monolithic file, costing 1,500 ms per operation.
- In contrast, on-demand lazy loading parses only the requested shard (e.g. `es/cli.yml` containing 2,121 keys) in 19.37 ms (a 60x speedup).
- Subsequent warm lookups within the same domain resolve in 0.004 ms.
- Loading a specific Modelo schema shard (e.g. `es/modelo/schema/303.yml` containing 2,713 keys) takes 42.48 ms, while leaving 44,186 keys in other Modelos completely unparsed and unallocated in memory.
- Single-leaf mutation on an isolated shard executes in 35.58 ms (a 42x speedup).

### 3. Evaluated sharding topologies

Four architectural approaches were evaluated:

- **Option A: Monolith retention with caching optimizations only.** Keeps 4 giant YAML files and relies exclusively on `._catalogue_cache` on-disk digests. Rejected: does not solve git merge collisions, 86k-line review fatigue, IDE editor stalls, or write-guard lock contention across disparate teams and Modelos.
- **Option B: Re-fragmentation into registry TOML trees.** Moving Casilla translations back to `registry/aeat/modelos/<id>/locales/*.toml`. Rejected: explicitly forbidden by `2026-08-04-modelo-localization-cascade-adr` and `aeat-locales-cli.md`. It re-couples schema definitions with language translations, breaks language-neutral schema compilation, and re-introduces parallel tooling.
- **Option C: Big-bang cutover without dual fallback.** Rejected: risks broken consumer paths during campaign transitions if ongoing tasks commit to monolithic files while sharded tooling is deploying.
- **Option D: Domain- and Modelo-sharded structure with smart routing, lazy loading, and dual-tier rollout fallback.** Chosen: shards each locale into top-level domain YAML files and a nested Modelo schema directory (`modelo/schema/<modelo_id>.yml`), routes keys via deterministic dot-notation mapping, parses shards on-demand, and transparently falls back to monolith files during the transition.

### 4. Deterministic key routing guarantees zero-ambiguity resolution

Key-to-shard mapping is deterministic and bijective in both directions:
```text
route_key_to_shard(dotted_key) -> Path:
  if dotted_key.startswith("modelo.schema.<id>.") -> modelo/schema/<id>.yml
  else if dotted_key.startswith("modelo.") -> modelo/general.yml
  else if dotted_key.startswith("<domain>.") for <domain> in (cli, errors, wizard, application, flows, docs, profile, adapters) -> <domain>.yml
  else -> common.yml
```
During catalogue loading, iterating `scan_directory(locales_dir / locale, pattern="*.yml")` and deep-merging all shard dictionaries reconstructs the exact unified logical dictionary.

A verification pass in `tmp/test_lazy_loader.py` executed across all 46,900 keys confirmed 100% key-and-value equivalence and identical type structure against the original monolithic catalogues.

### 5. Seamless integration with `dev.locales` and `cadrumo.core.i18n`

The sharded architecture fits into the existing layers:
- `dev/locales/manager.py`: `LocaleManager` loads sharded directory trees, addresses specific shards during `set_locale_value` / `remove_locale_value`, performs shard-level atomic rewrites under `catalogue_write_guard`, and preserves the global `get_codebase_keys()` discovery mesh (`_ast_scanner`, `_fstring_registry`, `_registry_scanner`).
- `dev/locales/_write_guard.py`: The lockfile `.catalogue-write.lock` remains at the root of `locales_dir`, while `CatalogueWriteGuard` records per-file content digests for observed shards.
- `src/cadrumo/locales/_intentional_identical.json`: Remains at `src/cadrumo/locales/_intentional_identical.json` as the unified cross-locale translation honesty allowlist.
- `src/cadrumo/core/i18n/_render.py`: `LazyLocaleCatalogue` resolves translations lazily, parsing only requested shards, and maintains the fast on-disk digest cache `read_catalogue_cache`.

## Sources

- Monolithic catalogue inventory: `src/cadrumo/locales/es.yml:1`, `src/cadrumo/locales/en.yml:1`, `src/cadrumo/locales/ca.yml:1`, `src/cadrumo/locales/hu.yml:1`
- Translation-honesty allowlist: `src/cadrumo/locales/_intentional_identical.json:1`
- Locale manager and write guard: `dev/locales/manager.py:190`, `dev/locales/_write_guard.py:88`, `dev/locales/_registry_scanner.py:63`
- Runtime renderer and catalogue cache: `src/cadrumo/core/i18n/_render.py:484`, `src/cadrumo/core/i18n/_catalogue_cache.py:1`
- Parity test suite: `src/cadrumo/tests/test_parity.py:1158`, `src/cadrumo/tests/test_locale_translation_honesty.py:287`
- Governing ADRs: `2026-08-04-modelo-localization-cascade-adr`, `2026-08-07-dev-harness-bleed-adr`, `2026-07-21-locale-key-resolution-adr`
- Sharding verification smoke tests: `tmp/smoke_test_sharding.py`, `tmp/smoke_test_prototype.py`, `tmp/test_lazy_loader.py`
- Online i18n large-scale YAML sharding patterns: https://phrase.com/blog/posts/yaml-i18n-best-practices/ and https://github.com/fnando/i18n-tasks
