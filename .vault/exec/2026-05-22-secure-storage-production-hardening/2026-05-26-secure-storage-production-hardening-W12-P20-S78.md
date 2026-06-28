---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S78'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
---



# `secure-storage-production-hardening` `W12.P20.S78`

Converted the active-profile runtime discovery production index into the first rollout register for Wave `W12`.

## Baseline

The source audit scanned `1415` Python files under `src/aeat` and found `467` files with storage/profile signals. The production subset contains `95` indexed files when grouped by current ownership:

- Adapter ownership: `33`
- Application ownership: `38`
- Domain ownership: `12`
- Core ownership: `3`
- CLI ownership: `9`

Two Spark discovery agents were launched for parallel confirmation, but both hit the current `gpt-5.3-codex-spark` usage limit before returning findings. The register below therefore uses the persisted mechanical audit plus fresh local `rg` scans as the authoritative S78 source.

## Adapter Ownership Register

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/adapters/outbound/aeat/auth/_session_store.py`, `src/aeat/adapters/outbound/aeat/auth/_authenticator.py` | raw secure-object session persistence and active-profile lookup | `runtime-default` | active bucket session, active route match, secure-object repository from runtime | migrate session-store tests to test runtime profile | registered for S79/S81 |
| `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` secure writes | direct secure-object writes around Clave Movil flow | `runtime-default` | runtime-bound repository after bootstrap custody opens session | split flow tests between bootstrap session setup and runtime write assertions | registered for S79/S81 |
| `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py` session acquisition | active-profile, manifest, and master-key session handling | `bootstrap-custody` | named bucket custody operation must open and close session explicitly | keep real bucket-session tests; do not use explicit DB URL as normal path | registered for S80/S81 |
| `src/aeat/adapters/outbound/aeat/browser/_factory.py` | active-profile identity for browser context | `runtime-default` | runtime-derived profile identity when storage-bound behavior is required | test browser context through active profile helper | registered for S81 |
| `src/aeat/adapters/outbound/aeat/sede/_observation_store.py` | `SecureBoundRepository` default and manual session activation | `runtime-default` | runtime-owned secure-bound repository; session activation belongs to custody/runtime policy | observation-store tests need active profile runtime | registered for S79/S81 |
| `src/aeat/adapters/outbound/aeat/sede/_declarations.py` | active-profile plus plain-file declaration state | `plaintext-exception` | classify file output as export/cache or migrate to runtime storage | tests must assert no sensitive alternate backend remains | registered for S96/S97 |
| `src/aeat/adapters/outbound/google/_oauth_flow.py`, `src/aeat/adapters/outbound/google/_records.py`, `src/aeat/adapters/outbound/google/_session_store.py`, `src/aeat/adapters/outbound/google/_profile_binding.py` | raw secure-object OAuth/session storage plus profile binding lookup | `runtime-default` | runtime-derived profile identity and secure-object repository | replace direct repository/route setup with test runtime profile | registered for S79/S80/S86 |
| `src/aeat/adapters/outbound/llm/_cache.py`, `src/aeat/adapters/outbound/llm/_usage.py` secure records | direct secure-object cache and usage writes | `runtime-default` | runtime-owned repository with active bucket readiness | cache/usage tests write through test runtime profile | registered for S79/S86 |
| `src/aeat/adapters/outbound/llm/_usage.py` file output | plain usage side state | `plaintext-exception` | classify as derived report/cache or migrate to secure namespace | tests must prove rebuild/export semantics if retained | registered for S96/S97 |
| `src/aeat/adapters/outbound/storage/_factory.py`, `src/aeat/adapters/outbound/storage/_google_drive.py`, `src/aeat/adapters/outbound/storage/_local.py` | outbound provider factory and local/remote mirror surfaces | `remote-mirror` | runtime-derived profile identity, namespace policy, encrypted mirror semantics | provider tests should bind a real runtime profile before mirror selection | registered for S98 |
| `src/aeat/adapters/persistence/profile/assets.py`, `src/aeat/adapters/persistence/profile/inventory.py` | legacy profile persistence backed by `SecureObjectRepository()` | `retired` | either remove legacy path or wrap behind runtime-owned migration adapter | tests should move to replacement profile/runtime API | registered for S79/S82 |
| `src/aeat/adapters/persistence/storage/attachment.py` | secure-object fallback plus plaintext attachment manifests | `plaintext-exception` | classify attachment metadata as accepted plaintext or secure-object migration | attachment tests must distinguish manifest metadata from encrypted payloads | registered for S96/S97 |
| `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py`, `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py`, `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py` | direct active master-key reads | `runtime-default` | consume key/session through runtime policy without bypassing readiness | cryptographic storage tests need live test bucket session | registered for S81 |
| `src/aeat/adapters/persistence/storage/blob_store/_materialisation.py`, `src/aeat/adapters/persistence/storage/master_key/_recovery.py` | file materialisation/recovery state | `bootstrap-custody` | custody operation owns file lifecycle and session availability | keep real recovery/materialisation tests isolated by bucket root | registered for S81/S96 |
| `src/aeat/adapters/persistence/storage/bucket/_layout.py`, `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py` | bucket layout and plaintext manifest IO | `manifest-discovery` | remain read/write primitives used by profile lifecycle and discovery, not encrypted runtime attachment | tests remain filesystem-real, not secure-object route tests | registered for S80 |
| `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`, `src/aeat/adapters/persistence/storage/envelope/_envelope.py` | `SecureBoundRepository` creates raw `SecureObjectRepository()` by default | `runtime-default` | default object repository must come from runtime-owned factory or explicit controlled injection | shared contract tests should use test runtime profile repository factory | registered for S79/S87 |
| `src/aeat/adapters/persistence/storage/master_key/_active_session.py`, `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`, `src/aeat/adapters/persistence/storage/master_key/_master_key.py` | active session, route disposal, manifest/key custody | `bootstrap-custody` | session lifecycle remains explicit but readiness result must feed `StorageRuntime` | master-key tests stay real and must avoid hiding cleanup failures | registered for S81 |
| `src/aeat/adapters/persistence/storage/runtime.py` | optional runtime inspector and repository builder | `runtime-default` | promote to required backend factory for profile-bound secure reads/writes | add test runtime helper and route/session refusal coverage | registered for S83-S95 |
| `src/aeat/adapters/persistence/storage/sql/engine.py`, `src/aeat/adapters/persistence/storage/sql/secure_objects.py` | settings-derived SQL engine and secure object repository | `runtime-default` | repository construction must enforce runtime readiness unless explicitly classified bootstrap/test | explicit-route tests limited to route refusal/classification behavior | registered for S79/S81/S94 |

## Application Ownership Register

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/application/auth/_apoderado.py`, `src/aeat/application/auth/_diagnostics.py`, `src/aeat/application/auth/_operator.py` | raw secure-object and secure-bound auth storage | `runtime-default` | active bucket runtime repository with route/session readiness | auth tests migrate to test runtime profile | registered for S79/S85 |
| `src/aeat/application/auth/_sessions.py` | active-profile and master-key session checks | `bootstrap-custody` | session-open path remains explicit and feeds runtime readiness | session tests keep real bucket session and profile helper | registered for S81 |
| `src/aeat/application/auth/_acquisition_lock.py` | active-profile keyed lock file | `plaintext-exception` | classify as ephemeral lock file with no sensitive payload or migrate | tests assert lock scope and cleanup under active profile root | registered for S96 |
| `src/aeat/application/calculations/_iva_compensation_history.py`, `src/aeat/application/calculations/_observations_repository.py` | `SecureBoundRepository` defaults | `runtime-default` | runtime-owned secure-bound repository factory | calculation repository tests use runtime repository fixture | registered for S79/S85 |
| `src/aeat/application/config_reset.py`, `src/aeat/application/diagnostics.py`, `src/aeat/application/repair_integrity.py` | mixed secure-object, manifest, route, and session inspection | `bootstrap-custody` | backend runtime policy must classify read-only diagnostics, repair custody, and destructive reset separately | diagnostics/repair tests keep real stores and assert refusal paths | registered for S80/S81/S82 |
| `src/aeat/application/evidence/_service.py`, `src/aeat/application/filing/_export.py`, `src/aeat/application/inventory/_service.py`, `src/aeat/application/invoices/_importing.py` | plain-file import/export/evidence state | `plaintext-exception` | classify each file store as export-only, cache, or secure-object migration | tests prove retained outputs are derived or non-sensitive | registered for S96/S97 |
| `src/aeat/application/filing/_history_repository.py`, `src/aeat/application/filing/_review.py` | secure-bound and secure-object filing persistence | `runtime-default` | runtime-owned repository default | filing tests write through active test profile runtime | registered for S79/S85 |
| `src/aeat/application/ledger/_actions.py` secure writes | direct secure-object ledger state | `runtime-default` | runtime-owned repository and namespace policy | ledger tests use test runtime profile | registered for S79/S85 |
| `src/aeat/application/ledger/_business_operation_invoice.py`, `src/aeat/application/ledger/_evidence.py` | bucket-local plain files | `plaintext-exception` | classify as secure migration, export-only, or accepted exception | tests must block sensitive alternate backend drift | registered for S96/S97 |
| `src/aeat/application/live/_borrador_100.py`, `src/aeat/application/live/_censo.py`, `src/aeat/application/live/_snapshot_base.py` secure records | direct secure-object or secure-bound live repositories | `runtime-default` | runtime-owned repository and active session readiness | live repository tests use profile runtime helper | registered for S79/S85 |
| `src/aeat/application/live/_expedientes.py`, `src/aeat/application/live/_notifications.py`, `src/aeat/application/live/_verify.py`, `src/aeat/application/live/_snapshot_base.py` file state | live AEAT plain-file stores | `plaintext-exception` | classify as cache/export or migrate to secure namespace | live tests assert retained files are rebuildable or redacted | registered for S96/S97 |
| `src/aeat/application/modelo/_reconcile.py`, `src/aeat/application/storage/calc_sheets/_records.py` | direct secure-object writes | `runtime-default` | runtime-bound repository and namespace registry | modelo/calc-sheet tests use test runtime profile | registered for S79/S85 |
| `src/aeat/application/modelo/_export.py` | active-profile plus export files | `plaintext-exception` | classify exports as derived artifacts separate from secure runtime | tests assert export is derived from secure source | registered for S96 |
| `src/aeat/application/state_projection.py`, `src/aeat/application/user_profile/_repository.py` | current best runtime adopters | `runtime-default` | preserve `inspect_bucket_storage_runtime(...)` as rollout pattern | extend tests as reference runtime behavior | registered for S83/S87 |
| `src/aeat/application/user_profile/_profile_repository.py`, `src/aeat/application/user_profile/_orchestration.py` | profile aggregate, manifest, pointer, encrypted profile record | `bootstrap-custody` | profile lifecycle owns cold-start and pointer/manifest writes; runtime attaches after session | profile lifecycle tests stay real and must prove rollback/consistency | registered for S80/S89/S90 |
| `src/aeat/application/workflow/_persistence.py`, `src/aeat/application/workflow/_models.py` secure state | raw secure-object workflow persistence plus active-profile helpers | `runtime-default` | first migration target: runtime-owned workflow repository | workflow tests migrate away from explicit DB route by default | registered for S79/S83 |
| `src/aeat/application/workflow/_profile_bucket_scan.py`, `src/aeat/application/workflow/_profile_health.py`, `src/aeat/diagnostics/profile.py` | manifest scan and active-profile health | `manifest-discovery` | remain plaintext discovery/readiness services, separate from encrypted runtime attachment | tests remain filesystem-real and verify discovery does not unlock storage | registered for S80/S90 |
| `src/aeat/application/wizard/_commands.py` | profile command orchestration with manifest/session/route handling | `bootstrap-custody` | profile create/switch bootstrap spans must use named profile lifecycle/runtime operations | wizard tests need bootstrap plus runtime-ready postconditions | registered for S81/S89 |

## Domain Ownership Register

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/domain/buckets/_event_repository.py` | raw secure-object event repository | `runtime-default` | runtime-owned repository factory; first migration target with workflow | bucket event tests use active test profile runtime | registered for S79/S83 |
| `src/aeat/domain/transactions/_repository.py`, `src/aeat/domain/invoices/_repository.py` | partial runtime-bound helper plus secure-bound repository surface | `runtime-default` | preserve and normalize `inspect_bucket_storage_runtime(...)` factory pattern | transaction/invoice tests use runtime helper, not injected engine | registered for S79/S84 |
| `src/aeat/domain/filing/_repository.py`, `src/aeat/domain/filing/_complementaria_repository.py`, `src/aeat/domain/submission/_repository.py`, `src/aeat/domain/justificante/_repository.py` | secure-bound/direct secure-object filing repositories | `runtime-default` | runtime-owned secure-bound defaults | filing/submission tests use test runtime profile | registered for S79/S84 |
| `src/aeat/domain/modelos/_calculation_repository.py`, `src/aeat/domain/modelos/_filing_repository.py`, `src/aeat/domain/modelos/_repository.py`, `src/aeat/domain/modelos/_verification_repository.py` | direct secure-object defaults | `runtime-default` | runtime repository factory plus namespace registry | modelo domain tests use test runtime profile | registered for S79/S84 |
| `src/aeat/domain/usage_ratios/_service.py` | direct secure-object service repository | `runtime-default` | runtime-owned repository default and namespace policy | usage ratio tests use test runtime profile | registered for S79/S84 |

## Core Ownership Register

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/core/_bucket_pointer_io.py` | active-profile pointer read/write | `manifest-discovery` | remain core pointer primitive; runtime consumes result but does not replace discovery | tests stay filesystem-real and validate precedence | registered for S80 |
| `src/aeat/core/config.py` | settings route derivation, route classification, active-profile precedence, outbound provider settings | `runtime-default` | keep as central settings source; runtime policy must consume typed route classification | explicit database URL tests remain approved only for route classification/refusal | registered for S81/S93 |
| `src/aeat/core/i18n/_render.py` | active-profile output-language resolver with safe fallback | `manifest-discovery` | read-only locale projection must not require encrypted runtime unlock | tests cover fallback without storage session | registered for S80/S81 |

## CLI Ownership Register

| Path or slice | Current API | Target type | Runtime requirement | Test isolation impact | Status |
| --- | --- | --- | --- | --- | --- |
| `src/aeat/entrypoints/cli/__init__.py`, `src/aeat/entrypoints/cli/_common.py` | root callback route/session guard and no-active-profile refusal | `bootstrap-custody` | replace transport-owned write-verb policy with backend runtime readiness/write-policy query | CLI tests assert backend refusal for root fallback and explicit route | registered for S81/S88 |
| `src/aeat/entrypoints/cli/_config/__init__.py` profile lifecycle commands | direct profile bootstrap, manifest scan, session, pointer, route handling | `bootstrap-custody` | profile create/switch/delete/logout go through named profile lifecycle/runtime operations | CLI profile tests keep real profile buckets and sessions | registered for S80/S81/S89 |
| `src/aeat/entrypoints/cli/_config/__init__.py` diagnostics/repair commands | secure-object diagnostics plus manifest/session inspection | `bootstrap-custody` | classify destructive repair/reset separately from read-only diagnostics | tests assert refusal and repair custody with real stores | registered for S82/S88 |
| `src/aeat/entrypoints/cli/_config/_google.py` | secure-object Google config plus provider settings | `remote-mirror` | runtime-derived profile identity before mirror/provider binding | provider CLI tests use runtime profile helper | registered for S86/S98 |
| `src/aeat/entrypoints/cli/_config/_profile_census.py`, `src/aeat/entrypoints/cli/_overview.py` | manifest/active-profile read-only display | `manifest-discovery` | remain read-only discovery/projection; no encrypted runtime unlock | CLI tests verify no-session display behavior | registered for S80/S90 |
| `src/aeat/entrypoints/cli/_app_live.py` | direct secure-object live app access | `runtime-default` | runtime-owned repository and readiness refusal | live CLI tests use active test profile runtime | registered for S79/S86/S91 |
| `src/aeat/entrypoints/cli/_ledger.py`, `src/aeat/entrypoints/cli/_modelo.py` | active-profile actor/guard logic and model route checks | `runtime-default` | backend runtime policy supplies readiness and active identity | ledger/modelo CLI tests cover profile selection and route refusal through runtime | registered for S81/S88/S91 |

## Follow-on Classification Contract

S78 deliberately does not close the detailed classification rows. It creates the grouped register that the next steps must refine:

- S79 owns every direct `SecureObjectRepository()` and `SecureBoundRepository` default.
- S80 owns pointer, manifest, and bucket scan callers.
- S81 owns SQL route, active-profile, and master-key session callers.
- S82 persists unresolved exceptions and owner rows before migration starts.

The migration phases should treat any register row left at `registered` as incomplete until one of the later steps marks the row migrated, retained with rationale, retired, or blocked with an owner.

## Validation

- Read the active-profile runtime discovery audit and the W12 plan rows.
- Ran fresh local `rg` scans for production secure-object, secure-bound, runtime, pointer, manifest, active-profile, SQL route, and master-key session signals.
- Parsed the production index into ownership counts: adapters `33`, application `38`, domain `12`, core `3`, CLI `9`.

## Review

The mandatory S78 review found no issues. It confirmed frontmatter compliance, register row-shape compliance, semantic-preserving plan schema repair, and full coverage of the `95` explicit production paths in the source audit index.
