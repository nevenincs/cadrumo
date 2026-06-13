---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S81'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P20-S78]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P20-S79]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P20-S80]]'
---



# `secure-storage-production-hardening` `W12.P20.S81`

Classified SQL route, active-profile, settings override, and master-key/session callers as runtime policy, bootstrap policy, or test-only setup.

## Scan Boundary

The scan covered direct calls or attribute access for:

- Active-profile policy: `resolve_active_bucket_id`, `active_bucket_id_or_raise`, `require_active_bucket_id`, `aeat_active_profile`, and `Settings(aeat_active_profile=...)`.
- SQL route policy: `aeat_database_url`, `Settings(aeat_database_url=...)`, `classify_storage_route`, `inspect_storage_runtime`, `inspect_bucket_storage_runtime`, and `settings_for_active_profile_bucket`.
- Session policy: `has_active_bucket_session`, `get_master_key_provider`, `activate_master_key_provider`, `activate_session`, and `get_active_master_key`.
- Settings spans: `override_settings` where used to bind active-profile, route, or session behavior.

Policy refs found:

- Production files: `41`
- Production refs: `140`
- Test files: `123`
- Test refs: `377`

S81 uses the plan's policy language and maps it onto the W12 target vocabulary:

- Runtime policy maps to `runtime-default`.
- Bootstrap policy maps to `bootstrap-custody`.
- Test-only setup maps to `test-runtime`.

## Adapter Production Policy

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/adapters/outbound/aeat/auth/_authenticator.py:1092`, `src/aeat/adapters/outbound/aeat/browser/_factory.py:120`, `src/aeat/adapters/outbound/aeat/sede/_declarations.py:346`, `src/aeat/adapters/outbound/google/_profile_binding.py:40` | active-profile identity/required-profile calls | `runtime-default` | identity consumers should receive active profile from runtime policy or profile binding service, not re-resolve ad hoc | adapter tests move to active test profile runtime | classified |
| `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py:733,748,751,753,754,839` | active-profile lookup, active-session check, settings override, master-key provider activation | `bootstrap-custody` | Clave Movil acquisition owns an explicit custody span that must hand a live session into runtime-bound writes | tests split custody setup from runtime write assertions | classified |
| `src/aeat/adapters/outbound/aeat/sede/_observation_store.py:224` | manual `activate_session` around observation storage | `bootstrap-custody` | manual session activation must become a named custody/runtime operation before repository writes | observation tests use real bucket session helper | classified |
| `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py:158`, `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py:91`, `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py:183` | `get_active_master_key` consumers | `runtime-default` | low-level encrypted storage may consume active key only through runtime/session readiness policy | crypto/blob/secret tests require live test bucket session | classified |
| `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py:203` | `Settings(aeat_database_url=...)` for engine disposal | `bootstrap-custody` | bucket-session cleanup may derive an explicit disposal route only inside session close custody | cleanup tests must surface disposal failures without `noqa` or swallowed exceptions | classified |
| `src/aeat/adapters/persistence/storage/master_key/_master_key.py:990,1271,1303` | session activation and active bucket fallback | `bootstrap-custody` | master-key provider opens and activates bucket sessions, then runtime consumes readiness | master-key tests stay real-behavior with explicit session assertions | classified |
| `src/aeat/adapters/persistence/storage/runtime.py:121,206,321,326,327,328` | route classification, bucket settings derivation, runtime inspection | `runtime-default` | this is the central runtime policy surface and should absorb caller readiness checks | runtime tests become the reference for route/session refusal | classified |
| `src/aeat/adapters/persistence/storage/sql/engine.py:118,156,182` | direct `aeat_database_url` route consumption | `runtime-default` | SQL engine remains the low-level route consumer; callers must arrive through runtime/settings policy | explicit database URL tests remain route-classification/refusal only | classified |
| `src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py:142` | shared test-suite `Settings(aeat_database_url=...)` | `test-runtime` | shared repository contract tests should use the sanctioned test runtime profile | migrate in S92/S93 | classified |

## Application Production Policy

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/application/auth/_acquisition_lock.py:79,165`, `src/aeat/application/auth/_operator.py:202`, `src/aeat/application/review/_operator.py:204` | required active-profile identity for app operations | `runtime-default` | application operations should consume active identity/readiness from runtime policy | tests use runtime profile helper instead of ad hoc active pointer setup | classified |
| `src/aeat/application/auth/_sessions.py:136,426,430,435,437` | required profile, active-session check, settings override, provider activation | `bootstrap-custody` | auth session open/read paths own a bootstrap custody span before runtime-bound storage access | auth session tests keep real bucket sessions | classified |
| `src/aeat/application/diagnostics.py:302,303,552`, `src/aeat/application/repair_integrity.py:1501,1504` | best-effort session/provider checks for diagnostics and repair | `bootstrap-custody` | diagnostics and repair must query backend readiness/custody policy without silently bypassing runtime | diagnostics/repair tests assert refusal and redaction paths | classified |
| `src/aeat/application/state_projection.py:420,676`, `src/aeat/application/user_profile/_repository.py:52`, `src/aeat/domain/invoices/_repository.py:34,44`, `src/aeat/domain/transactions/_repository.py:36` | `inspect_bucket_storage_runtime` and active-profile route binding | `runtime-default` | preserve as current best runtime-bound pattern and normalize other repositories to it | repository tests migrate to runtime helper | classified |
| `src/aeat/application/user_profile/_orchestration.py:427,464` | active-profile checks around profile lifecycle orchestration | `bootstrap-custody` | profile lifecycle owns create/switch/delete custody before runtime attachment | lifecycle tests prove pointer/session consistency | classified |
| `src/aeat/application/wizard/_commands.py:543,544,670,677,678,738` | master-key provider activation and settings overrides in wizard/profile setup | `bootstrap-custody` | wizard bootstrap must move behind named lifecycle/runtime operations | wizard tests assert bootstrap postconditions with real bucket sessions | classified |
| `src/aeat/application/wizard/_status.py:99,165,175`, `src/aeat/application/workflow/_models.py:209,224,234,261,280`, `src/aeat/diagnostics/profile.py:70,136` | active-profile projection and helper APIs | `runtime-default` | helper/projection APIs should become thin consumers of central active-profile/runtime policy | tests verify no duplicate authority with `WorkflowState.active_profile` | classified |
| `src/aeat/application/workflow/_profile_health.py:87,323,325` | settings active-profile plus session/provider checks for health | `bootstrap-custody` | health/repair must query runtime readiness and custody safely without unlocking unless required | profile-health tests keep explicit no-session and live-session cases | classified |

## Core Production Policy

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/core/_bucket_pointer_io.py:79` | `settings.aeat_active_profile` precedence | `runtime-default` | core remains the single precedence reader for active-profile override/pointer resolution | active-profile resolution tests remain approved core behavior | classified |
| `src/aeat/core/config.py:941,943,1185` | `aeat_database_url` and `aeat_active_profile` route derivation/classification | `runtime-default` | settings remains the centralized route definition surface consumed by `StorageRuntime` | explicit route tests remain core/refusal scope | classified |
| `src/aeat/core/i18n/_render.py:102,104` | active-profile/database route fields for locale resolver diagnostics | `runtime-default` | locale rendering may inspect settings safely but must not own storage readiness policy | i18n tests cover fallback without active storage unlock | classified |

## CLI Production Policy

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/entrypoints/cli/__init__.py:109,155,206,211,220,232,234` | root callback settings override, active-profile checks, route classification, session/provider bootstrap | `bootstrap-custody` | root callback policy must move to backend runtime readiness/write-policy while preserving bootstrap exemptions | CLI tests assert backend refusal for root fallback and explicit route | classified |
| `src/aeat/entrypoints/cli/_common.py:87,96,180`, `src/aeat/entrypoints/cli/_app_live.py:519`, `src/aeat/entrypoints/cli/_overview.py:47` | active-profile refusal and projection helpers | `runtime-default` | common CLI helpers should consume backend runtime policy/readiness | CLI tests verify translated no-active-profile and route refusal messages | classified |
| `src/aeat/entrypoints/cli/_config/__init__.py:134,221,303,345,473,522,655,742,859,905,909,910,952,1008,1009,1068,1119,1122,1123,1288,1295,1296,1607` | profile lifecycle, repair, and session/provider bootstrap | `bootstrap-custody` | profile create/switch/delete/logout/repair must use named lifecycle/runtime operations, not transport-owned storage spans | CLI lifecycle tests keep real profiles and sessions | classified |
| `src/aeat/entrypoints/cli/_config/_profile_census.py:30` | active-profile census lookup | `runtime-default` | census reads active identity through central policy and manifest discovery | census tests verify no unlock display behavior | classified |
| `src/aeat/entrypoints/cli/_ledger.py:366,392,464,531,635,667,691,716,742,776,834,882,1301,1530,1537,1720,1737,1740` | repeated active-profile actor/default resolution | `runtime-default` | ledger commands should receive active identity from runtime policy rather than repeated direct resolution | ledger tests migrate actor/profile setup to runtime helper | classified |
| `src/aeat/entrypoints/cli/_modelo.py:140,162,235,247,2915` | active-profile guards and required active bucket for modelo commands | `runtime-default` | modelo command guards should consume backend runtime readiness/refusal | modelo CLI tests cover profile selection and explicit route refusal through runtime | classified |

## Test-Only Setup Inventory

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| Adapter outbound tests: `src/aeat/adapters/outbound/aeat`, `src/aeat/adapters/outbound/llm` | `Settings(aeat_database_url=...)`, `override_settings`, live active-profile/session helpers | `test-runtime` | create real isolated profile runtime for storage-backed adapter tests; keep live smoke gates explicit | migrate direct route setup in S92/S93 | classified |
| Adapter persistence tests: `src/aeat/adapters/persistence/profile`, `src/aeat/adapters/persistence/storage` | explicit database URLs, runtime inspection tests, active session activation | `test-runtime` | storage runtime tests remain reference refusal coverage; repository roundtrips move to test runtime profile | migrate non-refusal explicit routes in S93 | classified |
| Application tests: `src/aeat/application` | explicit database URLs and settings overrides across auth, calculations, ledger, live, modelo, profile, workflow, diagnostics, and repair | `test-runtime` | use sanctioned profile runtime for real storage behavior while preserving route/refusal tests | migrate in S93 with focused exceptions | classified |
| Core and diagnostics tests: `src/aeat/core`, `src/aeat/diagnostics` | route classification, settings overrides, secure-object diagnostics setup | `test-runtime` | core route classification remains approved explicit-route scope; diagnostics storage moves to runtime helper | classify approved route/refusal exceptions in S95 | classified |
| Domain tests: `src/aeat/domain` | explicit database URLs, override settings, active session setup | `test-runtime` | domain repository tests should use runtime helper unless asserting route/session refusal | migrate in S93 after helper lands | classified |
| CLI tests: `src/aeat/entrypoints/cli` | profile/session provider setup, explicit database URLs, active-profile assertions | `test-runtime` | CLI tests should drive backend runtime policy through real profile buckets and live sessions | migrate after S88-S92 policy/helper work | classified |
| Shared test helper: `src/aeat/tests/secure_sql.py`, `src/aeat/tests/test_config.py`, `src/aeat/tests/test_secure_sql.py` | current explicit SQL route helper and session checks | `test-runtime` | helper should become or delegate to sanctioned runtime profile setup; explicit SQL remains route-refusal scope only | migrate in S92/S93 | classified |

Test setup refs by scan category:

- Active-profile refs: `test` slice contributes direct active-profile helper assertions and route derivation setup.
- Session refs: `test` slice contributes active master-key/provider/session setup.
- Route refs: `test` slice contributes explicit `Settings(aeat_database_url=...)` and route classification.
- Override refs: `test` slice contributes `override_settings(...)` for active profile, storage roots, sessions, and route behavior.

## Follow-on Work

- S82 must persist unresolved exception rows before migration starts.
- S88 must replace CLI transport-owned guarded-route policy with backend runtime policy.
- S89 must move profile lifecycle storage spans behind named lifecycle/runtime operations.
- S92/S93 must introduce and roll out the sanctioned test runtime profile helper.
- S95 must list the remaining approved explicit-route tests after migration.

## Validation

- Ran AST scan for active-profile, SQL route, session, and settings-span signals across `src/aeat`.
- Classified `41` production files with `140` refs.
- Classified the test-only setup surface as `123` files with `377` refs grouped by ownership slice.
- Ran `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`.
- Ran `uv run --no-sync ruff check src/aeat/application/user_profile/_censo_errors.py`.
- Ran `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py -q`.

## Review

The mandatory S81 review found no classification defects. It identified one stale deprecated command reference in `src/aeat/application/user_profile/_censo_errors.py`; that source docstring now points to `aeat config profile create NAME` instead of the retired init wording. A follow-up source scan found only the explicit regression-test docstring asserting that `config init` is not reintroduced.
