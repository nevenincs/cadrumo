---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S79'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P20-S78]]'
---



# `secure-storage-production-hardening` `W12.P20.S79`

Classified each no-arg `SecureObjectRepository()` default and each inherited `SecureBoundRepository` default found under `src/aeat`.

## Scan Boundary

The classification used AST discovery rather than text-only matching:

- Included no-argument `SecureObjectRepository()` calls.
- Included classes that inherit from `SecureBoundRepository[...]` because the base class currently defaults to raw `SecureObjectRepository()`.
- Excluded `SecureObjectRepository(engine=...)` calls from this step because those are explicit engine/test-route sites owned by S93, except for noting that the runtime-owned factory path is already explicit.

Default sites classified: `75`.

- Production `runtime-default`: `50`
- Production `bootstrap-custody`: `7`
- Production `retired`: `3`
- Test/support `test-runtime`: `15`

## Adapter Defaults

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py:1450` | `SecureObjectRepository()` | `runtime-default` | repository must come from active bucket runtime after custody/session setup | Clave Movil tests split custody setup from runtime write assertions | classified |
| `src/aeat/adapters/outbound/aeat/auth/_session_store.py:40,51,64,78` | repeated `SecureObjectRepository()` calls | `runtime-default` | AEAT auth session store must bind to active bucket runtime repository | session store roundtrips migrate to test runtime profile | classified |
| `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py:637` | test default `SecureObjectRepository()` call | `test-runtime` | test should create repositories through sanctioned test runtime profile | remove raw default test construction in S93 | classified |
| `src/aeat/adapters/outbound/aeat/sede/_observation_store.py:42` | `objects or SecureObjectRepository()` | `runtime-default` | observation repository default comes from runtime-owned factory | tests keep explicit injection only through runtime fixture | classified |
| `src/aeat/adapters/outbound/google/_session_store.py:37,50,64,77,91,104,118,131,149` | repeated `SecureObjectRepository()` calls | `runtime-default` | Google OAuth/session storage uses runtime-derived repository and profile identity | OAuth/session tests migrate to runtime profile helper | classified |
| `src/aeat/adapters/outbound/llm/_cache.py:83,156,181,200` | repeated `SecureObjectRepository()` calls | `runtime-default` | cache repository writes through active bucket runtime | cache roundtrips migrate to test runtime profile | classified |
| `src/aeat/adapters/outbound/llm/_usage.py:106,134` | repeated `SecureObjectRepository()` calls | `runtime-default` | usage records write through active bucket runtime | usage tests migrate to runtime profile helper | classified |
| `src/aeat/adapters/persistence/profile/assets.py:104,205` | legacy profile `SecureObjectRepository()` calls | `retired` | legacy profile persistence is removed or wrapped as an explicit migration adapter | legacy roundtrips move to replacement profile lifecycle/runtime API | classified |
| `src/aeat/adapters/persistence/profile/inventory.py:119` | `objects if objects is not None else SecureObjectRepository()` | `retired` | legacy profile inventory default is removed or migration-wrapped | inventory tests migrate to current profile lifecycle/runtime API | classified |
| `src/aeat/adapters/persistence/storage/attachment.py:73` | `self.objects or SecureObjectRepository()` | `runtime-default` | secure attachment object writes use runtime repository; plaintext manifest side is S96/S97 | attachment roundtrips use runtime repository fixture | classified |
| `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py:72` | `objects or SecureObjectRepository()` in base class | `runtime-default` | base default must become runtime-owned or require explicit approved object repository | all bound repository contract tests move to runtime fixture | classified |
| `src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py:244` | test-suite helper `SecureObjectRepository()` | `test-runtime` | contract helper should create repositories through sanctioned test runtime profile | shared suite becomes runtime-profile backed | classified |
| `src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py:44`, `src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository_contract.py:57` | test-only `SecureBoundRepository` subclasses | `test-runtime` | test subclasses remain allowed only behind runtime-backed test repository factory | direct raw default is removed from test setup | classified |

`src/aeat/adapters/persistence/storage/runtime.py` already calls `SecureObjectRepository(engine=engine)` inside the runtime-owned factory and was intentionally excluded from no-arg default counts.

## Application Defaults

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/application/auth/_apoderado.py:73` | `_ApoderadoConfigRepository` inherits `SecureBoundRepository` | `runtime-default` | auth config repository default comes from runtime-owned secure-bound factory | auth config tests use runtime profile helper | classified |
| `src/aeat/application/auth/_diagnostics.py:111,143,157,173` | repeated `SecureObjectRepository()` diagnostics reads/writes | `runtime-default` | diagnostics reads through active runtime with translated readiness refusal | diagnostics tests assert runtime refusal instead of raw route errors | classified |
| `src/aeat/application/auth/_operator.py:275` | `SecureObjectRepository().save_many(...)` | `runtime-default` | operator auth state/catalogue writes use runtime-owned repository | operator tests use active profile runtime | classified |
| `src/aeat/application/calculations/_iva_compensation_history.py:196` | `IvaCompensationHistoryRepository` inherits `SecureBoundRepository` | `runtime-default` | compensation history default comes from runtime-owned bound factory | calculation history tests use runtime repository fixture | classified |
| `src/aeat/application/calculations/_observations_repository.py:141,203` | calculation and wallet repositories inherit `SecureBoundRepository` | `runtime-default` | observation/wallet defaults come from runtime-owned bound factory | observation tests use runtime profile helper | classified |
| `src/aeat/application/diagnostics.py:804` | `SecureObjectRepository()` inside diagnostics | `bootstrap-custody` | diagnostic storage inspection must call backend runtime readiness/custody policy | diagnostics tests keep real stores and assert no unlock bypass | classified |
| `src/aeat/application/filing/_history_repository.py:20` | `ModeloHistoryRepository` inherits `SecureBoundRepository` | `runtime-default` | filing history default comes from runtime-owned bound factory | filing history tests use runtime profile helper | classified |
| `src/aeat/application/live/_borrador_100.py:150` | `objects or SecureObjectRepository()` | `runtime-default` | live borrador repository default comes from runtime-owned factory | live tests use runtime profile helper | classified |
| `src/aeat/application/live/_censo.py:190` | `objects or SecureObjectRepository()` | `runtime-default` | censo repository default comes from runtime-owned factory | live/censo tests use runtime profile helper | classified |
| `src/aeat/application/modelo/_reconcile.py:271` | `SecureObjectRepository().save_many(...)` | `runtime-default` | modelo reconciliation writes through active runtime repository | modelo reconciliation tests use runtime profile helper | classified |
| `src/aeat/application/repair_integrity.py:509,675,716,781,957,1544` | repair bound repository plus repeated `SecureObjectRepository()` construction | `bootstrap-custody` | repair operations need explicit backend custody policy before opening repositories | repair tests keep real stores and assert readiness/refusal paths | classified |
| `src/aeat/application/workflow/_persistence.py:56,250` | workflow `SecureObjectRepository()` defaults | `runtime-default` | workflow state/run persistence is first migration target for runtime-owned repository | workflow persistence tests migrate to test runtime profile | classified |
| `src/aeat/application/filing/test_complementaria_repository.py:151`, `src/aeat/application/filing/test_history_repository.py:118`, `src/aeat/application/filing/test_repository.py:153` | test default `SecureObjectRepository()` calls | `test-runtime` | tests should create repositories through sanctioned test runtime profile | remove raw default test construction in S93 | classified |

## Domain Defaults

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/domain/buckets/_event_repository.py:28` | `objects or SecureObjectRepository()` | `runtime-default` | bucket-event history repository default comes from runtime-owned factory | bucket-event tests use runtime profile helper | classified |
| `src/aeat/domain/filing/_complementaria_repository.py:37` | `SecureObjectRepository()` | `runtime-default` | complementaria repository default comes from runtime-owned factory | complementaria tests use runtime profile helper | classified |
| `src/aeat/domain/filing/_repository.py:20` | `ModeloDraftRepository` inherits `SecureBoundRepository` | `runtime-default` | modelo draft default comes from runtime-owned bound factory | filing tests use runtime profile helper | classified |
| `src/aeat/domain/justificante/_repository.py:29` | `JustificanteRepository` inherits `SecureBoundRepository` | `runtime-default` | justificante default comes from runtime-owned bound factory | justificante tests use runtime profile helper | classified |
| `src/aeat/domain/modelos/_calculation_repository.py:28` | `objects or SecureObjectRepository()` | `runtime-default` | modelo calculation default comes from runtime-owned factory | modelo tests use runtime profile helper | classified |
| `src/aeat/domain/modelos/_filing_repository.py:29` | `objects or SecureObjectRepository()` | `runtime-default` | filing record default comes from runtime-owned factory | modelo filing tests use runtime profile helper | classified |
| `src/aeat/domain/modelos/_repository.py:44` | `objects or SecureObjectRepository()` | `runtime-default` | modelo work-unit default comes from runtime-owned factory | modelo repository tests use runtime profile helper | classified |
| `src/aeat/domain/modelos/_verification_repository.py:28` | `objects or SecureObjectRepository()` | `runtime-default` | verification default comes from runtime-owned factory | verification tests use runtime profile helper | classified |
| `src/aeat/domain/submission/_repository.py:23` | `SubmissionRepository` inherits `SecureBoundRepository` | `runtime-default` | submission default comes from runtime-owned bound factory | submission tests use runtime profile helper | classified |
| `src/aeat/domain/usage_ratios/_service.py:58,130` | `objects or SecureObjectRepository()` service defaults | `runtime-default` | usage-ratio service writes through runtime-owned repository | usage-ratio tests use runtime profile helper | classified |
| `src/aeat/domain/justificante/test_repository.py:149` | test default `SecureObjectRepository()` call | `test-runtime` | test should use sanctioned runtime profile helper | remove raw default test construction in S93 | classified |

`src/aeat/domain/invoices/_repository.py` and `src/aeat/domain/transactions/_repository.py` remain in later migration scope, but this scan found no no-arg repository default in those files; their current helper path already uses `inspect_bucket_storage_runtime(...)`.

## CLI Defaults

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/entrypoints/cli/_config/_google.py:625` | `SecureObjectRepository()` | `runtime-default` | CLI Google config writes through runtime repository before mirror/provider binding | CLI Google tests use runtime profile helper | classified |
| `src/aeat/entrypoints/cli/_config/test_repair_reset_state.py:71` | test default `SecureObjectRepository()` call | `test-runtime` | test should use sanctioned runtime profile helper unless asserting bootstrap/refusal | remove raw default test construction in S93 | classified |
| `src/aeat/entrypoints/cli/test_repair_privacy_contract.py:74,111,185,216,225,230` | repeated test default `SecureObjectRepository()` calls | `test-runtime` | repair privacy tests should build real repositories through test runtime helper | remove raw default test construction in S93 | classified |

## Follow-on Work

- S83 and S85 own the first production runtime migrations for workflow, bucket events, and application repositories.
- S84 owns the domain repository migrations.
- S86 owns adapter and outbound repository migrations.
- S92 and S93 own the test runtime helper and migration of default/explicit engine test construction.
- S94 should convert this S79 scan into a guard that blocks new production no-arg repository defaults outside the approved runtime factory.

## Validation

- Ran the W12 plan checker before classification.
- Ran `rg` scans for direct `SecureObjectRepository()` and `SecureBoundRepository` inheritance.
- Ran AST classification for no-argument `SecureObjectRepository()` calls and `SecureBoundRepository[...]` subclasses across `src/aeat`.

## Review

The mandatory S79 review found one missing no-argument repository default in `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py`. The row was added as `test-runtime`. Follow-up review found stale category totals after that repair; the totals were corrected to `runtime-default: 50`, `bootstrap-custody: 7`, `retired: 3`, and `test-runtime: 15`.
