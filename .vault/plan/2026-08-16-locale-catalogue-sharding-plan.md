---
tags:
  - '#plan'
  - '#locale-catalogue-sharding'
date: '2026-08-16'
modified: '2026-08-16'
body_hash: 'sha256:97fb3e1c8b3f2e7642964897d870e5b5df3c58ca5539c571e7f87246cbb68cd5'
tier: L2
related:
  - '[[2026-08-16-locale-catalogue-sharding-adr]]'
  - '[[2026-08-16-locale-catalogue-sharding-research]]'
---

# `locale-catalogue-sharding` plan

Domain-sharded locale catalogue rollout with on-demand lazy loading, deterministic dot-notation routing, and dual-tier transitional fallback.

## Description

This plan implements the domain- and Modelo-sharded localization architecture authorized in `2026-08-16-locale-catalogue-sharding-adr`. It replaces 4 monolithic 4 MB YAML files (~46,900 keys across 86,000 lines) with structured per-language directory trees (`locales/<locale>/<domain>.yml` and `locales/<locale>/modelo/schema/<modelo_id>.yml`), adds smart dot-notation key routing, introduces on-demand lazy shard loading in `cadrumo.core.i18n`, and enhances `dev.locales` maintenance tooling.

Because catalogue migration is a destructive storage boundary, the rollout follows an explicit 4-phase staged cadence:
1. Additive engine readiness (routing & lazy loader supporting dual fallback).
2. Additive tooling upgrades & shard tree materialization.
3. Strict parity attestation proving 100% key-value match across both stores.
4. Atomic single-commit rollover: switching runtime resolution to primary shard mode, removing the 4 legacy monolithic files, and synchronizing rules without leaving permanent legacy bridges (`no-legacy-compatibility`, `aeat-architecture-boundaries`).

## Steps

### Phase `P01` - routing and lazy runtime loading

Deliver deterministic dot-notation key routing and on-demand lazy shard resolution with dual-tier fallback in core i18n (additive only, zero deletions).

- [x] `P01.S01` - Implement deterministic `route_key_to_shard` and domain shard taxonomy; `src/cadrumo/core/i18n/_routing.py`.
- [x] `P01.S02` - Implement `LazyLocaleCatalogue` with on-demand shard parsing, in-memory caching, and dual-tier monolith fallback; `src/cadrumo/core/i18n/_render.py`.
- [x] `P01.S03` - Add directory-aware multi-file digest computation and cache invalidation; `src/cadrumo/core/i18n/_catalogue_cache.py`.
- [x] `P01.S04` - Add targeted unit tests for lazy loading, cache hits, and dual fallback resolution; `src/cadrumo/core/i18n/tests/test_lazy_render.py`.

### Phase `P02` - maintenance harness upgrades

Enhance `dev.locales` manager, write guard, and CLI commands to operate natively over directory-based shards (additive only).

- [x] `P02.S05` - Update `LocaleManager.load_locale` and `load_sharded_locale` with deep dictionary merging; `dev/locales/manager.py`.
- [x] `P02.S06` - Upgrade `LocaleManager.set_locale_value`, `set_locale_values`, and `remove_locale_value` to mutate targeted shards; `dev/locales/manager.py`.
- [x] `P02.S07` - Upgrade `LocaleManager.scaffold` to partition codebase keys by shard path and prune per-shard; `dev/locales/manager.py`.
- [x] `P02.S08` - Update `CatalogueWriteGuard` to fingerprint and lock sharded file paths under write guard; `dev/locales/_write_guard.py`.
- [x] `P02.S09` - Add test coverage for sharded CLI scaffold, audit, set, and remove commands; `dev/locales/tests/test_sharded_manager.py`.

### Phase `P03` - catalogue materialization and pre-cutover attestation

Materialize sharded directory trees alongside existing monoliths and prove 100% key-value parity across all 4 locales.

- [x] `P03.S10` - Partition and write `es`, `en`, `ca`, and `hu` monolithic files into `src/cadrumo/locales/<locale>/` shard trees while preserving monoliths; `src/cadrumo/locales/`.
- [x] `P03.S11` - Run `python -m dev.locales audit` and `scaffold --check` across sharded catalogues to prove zero key drift; `dev/locales/cli.py`.
- [x] `P03.S12` - Execute targeted parity gates asserting exact key-value match and translation honesty; `src/cadrumo/tests/test_parity.py`.

### Phase `P04` - atomic cutover and legacy monolith deletion

Execute the atomic rollover in a single coordinated transition, deleting the legacy monolithic files and updating rule references.

- [x] `P04.S13` - Switch runtime catalogue resolution to primary shard mode; `src/cadrumo/core/i18n/_render.py`.
- [x] `P04.S14` - Atomically delete legacy monolithic files `src/cadrumo/locales/{es,en,ca,hu}.yml`; `src/cadrumo/locales/`.
- [x] `P04.S15` - Update rule `.vaultspec/rules/aeat-locales-cli.md` and run `vaultspec-core sync` to record sharded directory authority; `.vaultspec/rules/aeat-locales-cli.md`.

## Parallelization

- Phase `P01` and Phase `P02` may be implemented concurrently as they touch disjoint modules (`src/cadrumo/core/i18n/` and `dev/locales/`).
- Phase `P03` requires both `P01` and `P02` to be complete before materialization.
- Phase `P04` is strictly blocked until all gates in `P03` attest 100% parity.

## Verification

1. **Pre-flight Gate:** Current worktree has no uncommitted mutations in `src/cadrumo/locales/` before materialization begins.
2. **Exact Parity:** 100.0% of the 46,900 translation keys in `es`, `en`, `ca`, and `hu` resolve to identical values through the lazy sharded loader.
3. **On-Demand Performance:** Querying `tr("cli.root.app_help")` parses only `cli.yml` in <30 ms, leaving Modelo schema keys unparsed and saving >90% memory.
4. **Dual Fallback During Rollout:** Keys added exclusively to monolithic files during active campaigns continue resolving seamlessly prior to `P04`.
5. **Atomic Deletion Verification:** Following `P04.S14`, zero monolithic `.yml` files remain in `src/cadrumo/locales/`, and `pytest src/cadrumo/tests/test_parity.py` passes cleanly against sharded directory trees.
6. **Rollback Circuit-Breaker:** If any test fails in `P03` or `P04.S13`, the sharded directories can be cleanly dropped with zero data loss since monoliths remain untouched until `P04.S14`.
