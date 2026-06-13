---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-21-profile-state-aggregate-adr]]'
  - '[[2026-05-21-profile-uuid-identity-adr]]'
  - '[[2026-05-07-user-profile-backend-schema-adr]]'
---



# Active-profile storage runtime discovery audit

## Scope

This audit covers the current secure-storage, bucket, active-profile, and persistence routing surface across every Python source file under `src/aeat`. The audit surface was `1415` Python files. The goal was to establish a hard baseline for centralising active-profile storage read/write orchestration behind a bespoke `StorageRuntime` surface rather than continuing to rely on loosely coordinated settings, pointer, session, repository, and CLI conventions.

The audit also read current storage/profile vault decisions and plans so the cleanup plan below aligns with accepted direction rather than inventing a new architecture.

## Coverage method

The codebase pass used a deterministic scanner over all `src/aeat/**/*.py` files. Every file was read once and categorized by regex signals for secure-object persistence, secure-bound repositories, storage runtime, active-profile resolution, pointer/manifest/bucket scans, master-key sessions, SQL route settings, legacy profile persistence, JSONL/plain-file persistence, and outbound storage providers.

Scanner totals:

- Python files scanned: `1415`
- Files with at least one storage/profile signal: `467`
- Production files with at least one signal: `169`
- Test files with at least one signal: `298`
- Files with no scanner signal: `948`

Category counts:

- `secure_object_repository`: all `146`, production `53`, test `93`
- `secure_bound_repository`: all `53`, production `30`, test `23`
- `storage_runtime`: all `5`, production `4`, test `1`
- `active_profile_resolution`: all `74`, production `34`, test `40`
- `pointer_manifest_bucket`: all `83`, production `41`, test `42`
- `master_key_session`: all `57`, production `32`, test `25`
- `settings_sql_route`: all `182`, production `20`, test `162`
- `plaintext_profile_storage`: all `9`, production `4`, test `5`
- `jsonl_or_plain_file_state`: all `223`, production `68`, test `155`
- `outbound_storage_provider`: all `15`, production `10`, test `5`

Spark Codex agents were invoked for persistence-backend discovery, CLI/profile discovery, application/domain discovery, and vault-context discovery. The vault-context agent completed and its findings are incorporated below. Two code-slice Spark agents hit the current `gpt-5.3-codex-spark` usage limit before returning usable findings, and one did not return before timeout. Therefore, the authoritative coverage baseline for code is the mechanical all-file scanner plus direct local inspection, not incomplete subagent output.

## High-level overview

The accepted architecture is clear: active profile selection is `--profile` or settings override, then `AEAT_ACTIVE_PROFILE`, then the plaintext `active-profile` pointer. The profile identity is the immutable UUID bucket id. The primary SQLite route should derive from the selected bucket at `buckets/<bucket-id>/db/aeat.db`, and secure reads/writes should require a live bucket session whose bucket matches that route.

The implementation now contains `StorageRuntime` in `src/aeat/adapters/persistence/storage/runtime.py`, but it is not yet the application-wide runtime surface. It currently inspects route/session readiness and can build a bucket-attached `SecureObjectRepository`. Most application and domain repositories still construct `SecureObjectRepository()` directly, rely on `Settings.aeat_database_url` side effects, or accept injected repositories in tests. The result is a partial hardening layer: strong primitives exist, but callers still pick from several competing APIs.

Profile lifecycle has progressed further than the rest of storage. `ProfileRepository` is already the sole writer for the physical profile aggregate: bucket directory, manifest, encrypted `UserProfileRecord`, bucket events, and active pointer. `UserProfileLifecycleRepository` now uses `inspect_bucket_storage_runtime(...)` when it needs a bucket-local secure-object repository. That is the best current adoption pattern.

The fragmented parts are elsewhere: workflow state, transactions, invoices, model work units, filing records, AEAT observations, auth sessions, Google OAuth, LLM cache/usage, usage ratios, and several live/ledger JSONL stores still bind storage through direct repository construction or direct file paths. Tests intensify this fragmentation by using explicit `aeat_database_url` and injected engines as their main sandboxing technique.

## Competing APIs currently wrangling storage/profile work

- `Settings` and `classify_storage_route(...)`: computes the primary SQL route from `aeat_database_url`, `aeat_active_profile`, pointer file, or root fallback. This is central but still exposed as a low-level settings mechanism.
- `resolve_active_bucket_id()`: reads the active profile chain in core. Many callers use it directly to branch, refuse, or derive actor/bucket ids.
- CLI root session activation: `_activate_active_bucket_session(...)` opens a bucket session opportunistically and contains its own guarded verb allowlist for root-fallback and explicit-route refusal.
- `get_master_key_provider(...)` and `activate_master_key_provider(...)`: open the crypto session. Profile create/switch/delete and some auth flows use this directly with `override_settings(...)`.
- `StorageRuntime`: validates route/session readiness and creates a bucket-attached secure-object repository. Current adoption is small.
- `SecureObjectRepository()`: the dominant persistence constructor. When called without an engine, it resolves `get_engine()` from settings; when injected with an engine, it bypasses active-profile route derivation and relies on tests/callers to bind the correct backend.
- `SecureBoundRepository`: typed envelope repository base. It usually defaults to `SecureObjectRepository()` internally, so it inherits the same runtime-fragmentation risk.
- `ProfileRepository`: cross-store profile aggregate writer. This is the strongest current centralisation point for profile lifecycle.
- Manifest scanners: `read_profile_bucket(...)`, `read_profile_bucket_by_id(...)`, and `list_profile_buckets(...)` enumerate plaintext manifests without unlocking encrypted storage. This is necessary for profile discovery but separate from secure-object runtime.
- Direct JSONL/plain-file stores: several application services still write bucket-keyed plaintext JSONL or JSON documents under settings-derived paths.
- Outbound storage provider factory: resolves a remote/local mirror provider from profile binding and settings. This is adjacent to, but separate from, secure-object runtime.

## Production signal index

Files below are production files with at least one storage/profile signal. Files not listed here were still scanned; they had no scanner signal under this audit vocabulary.

- `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`: active-profile resolution
- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`: secure-object repository, active-profile resolution, pointer/manifest/bucket, master-key session
- `src/aeat/adapters/outbound/aeat/auth/_session_store.py`: secure-object repository
- `src/aeat/adapters/outbound/aeat/browser/_factory.py`: active-profile resolution
- `src/aeat/adapters/outbound/aeat/sede/_declarations.py`: active-profile resolution, plain-file state
- `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`: secure-object repository, secure-bound repository, master-key session
- `src/aeat/adapters/outbound/google/_oauth_flow.py`: secure-object repository, pointer/manifest/bucket
- `src/aeat/adapters/outbound/google/_profile_binding.py`: active-profile resolution
- `src/aeat/adapters/outbound/google/_records.py`: secure-object repository
- `src/aeat/adapters/outbound/google/_session_store.py`: secure-object repository
- `src/aeat/adapters/outbound/llm/_cache.py`: secure-object repository
- `src/aeat/adapters/outbound/llm/_usage.py`: secure-object repository, plain-file state
- `src/aeat/adapters/outbound/storage/_factory.py`: outbound storage provider
- `src/aeat/adapters/outbound/storage/_google_drive.py`: outbound storage provider
- `src/aeat/adapters/outbound/storage/_local.py`: plain-file state, outbound storage provider
- `src/aeat/adapters/persistence/profile/assets.py`: secure-object repository, legacy profile persistence
- `src/aeat/adapters/persistence/profile/inventory.py`: secure-object repository, legacy profile persistence
- `src/aeat/adapters/persistence/storage/attachment.py`: secure-object repository, secure-bound repository, pointer/manifest/bucket, plain-file state
- `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py`: secure-bound repository, master-key session, plain-file state
- `src/aeat/adapters/persistence/storage/blob_store/_materialisation.py`: master-key session, plain-file state
- `src/aeat/adapters/persistence/storage/bucket/_layout.py`: pointer/manifest/bucket, plain-file state
- `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`: pointer/manifest/bucket, plain-file state
- `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`: secure-object repository, master-key session
- `src/aeat/adapters/persistence/storage/envelope/_envelope.py`: secure-bound repository, plain-file state
- `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`: secure-object repository, secure-bound repository
- `src/aeat/adapters/persistence/storage/master_key/_active_session.py`: master-key session
- `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`: master-key session, SQL route settings
- `src/aeat/adapters/persistence/storage/master_key/_master_key.py`: secure-object repository, active-profile resolution, pointer/manifest/bucket, master-key session, plain-file state
- `src/aeat/adapters/persistence/storage/master_key/_recovery.py`: plain-file state
- `src/aeat/adapters/persistence/storage/runtime.py`: secure-object repository, storage runtime, active-profile resolution, pointer/manifest/bucket, SQL route settings
- `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py`: secure-bound repository, master-key session, plain-file state
- `src/aeat/adapters/persistence/storage/sql/engine.py`: SQL route settings, plain-file state
- `src/aeat/adapters/persistence/storage/sql/secure_objects.py`: secure-object repository, master-key session, SQL route settings, outbound storage provider
- `src/aeat/application/auth/_acquisition_lock.py`: active-profile resolution, plain-file state
- `src/aeat/application/auth/_apoderado.py`: secure-object repository, secure-bound repository
- `src/aeat/application/auth/_diagnostics.py`: secure-object repository
- `src/aeat/application/auth/_operator.py`: secure-object repository, active-profile resolution, pointer/manifest/bucket
- `src/aeat/application/auth/_sessions.py`: active-profile resolution, master-key session
- `src/aeat/application/calculations/_iva_compensation_history.py`: secure-bound repository
- `src/aeat/application/calculations/_observations_repository.py`: secure-object repository, secure-bound repository
- `src/aeat/application/config_reset.py`: secure-object repository, pointer/manifest/bucket, SQL route settings
- `src/aeat/application/diagnostics.py`: secure-object repository, active-profile resolution, pointer/manifest/bucket, master-key session, SQL route settings
- `src/aeat/application/evidence/_service.py`: plain-file state
- `src/aeat/application/filing/_export.py`: plain-file state
- `src/aeat/application/filing/_history_repository.py`: secure-bound repository
- `src/aeat/application/filing/_review.py`: secure-object repository
- `src/aeat/application/inventory/_service.py`: plain-file state
- `src/aeat/application/invoices/_importing.py`: plain-file state
- `src/aeat/application/ledger/_actions.py`: secure-object repository, plain-file state
- `src/aeat/application/ledger/_business_operation_invoice.py`: plain-file state
- `src/aeat/application/ledger/_evidence.py`: plain-file state
- `src/aeat/application/live/_borrador_100.py`: secure-object repository, secure-bound repository
- `src/aeat/application/live/_censo.py`: secure-object repository, secure-bound repository
- `src/aeat/application/live/_expedientes.py`: plain-file state
- `src/aeat/application/live/_notifications.py`: plain-file state
- `src/aeat/application/live/_snapshot_base.py`: secure-object repository, plain-file state
- `src/aeat/application/live/_verify.py`: plain-file state
- `src/aeat/application/modelo/_export.py`: active-profile resolution, plain-file state
- `src/aeat/application/modelo/_reconcile.py`: secure-object repository, active-profile resolution
- `src/aeat/application/repair_integrity.py`: secure-object repository, secure-bound repository, pointer/manifest/bucket, master-key session, legacy profile persistence
- `src/aeat/application/state_projection.py`: storage runtime, active-profile resolution, pointer/manifest/bucket
- `src/aeat/application/storage/calc_sheets/_records.py`: secure-object repository
- `src/aeat/application/user_profile/_orchestration.py`: secure-object repository, active-profile resolution, pointer/manifest/bucket, plain-file state
- `src/aeat/application/user_profile/_profile_repository.py`: secure-object repository, pointer/manifest/bucket, SQL route settings, plain-file state
- `src/aeat/application/user_profile/_repository.py`: secure-object repository, secure-bound repository, storage runtime
- `src/aeat/application/wizard/_commands.py`: active-profile resolution, pointer/manifest/bucket, master-key session, SQL route settings
- `src/aeat/application/workflow/_models.py`: secure-object repository, active-profile resolution, pointer/manifest/bucket
- `src/aeat/application/workflow/_persistence.py`: secure-object repository, secure-bound repository, active-profile resolution, master-key session, SQL route settings
- `src/aeat/application/workflow/_profile_bucket_scan.py`: pointer/manifest/bucket
- `src/aeat/application/workflow/_profile_health.py`: active-profile resolution, pointer/manifest/bucket, master-key session, plain-file state
- `src/aeat/core/_bucket_pointer_io.py`: active-profile resolution, pointer/manifest/bucket, plain-file state
- `src/aeat/core/config.py`: active-profile resolution, pointer/manifest/bucket, SQL route settings, plain-file state, outbound storage provider
- `src/aeat/core/i18n/_render.py`: active-profile resolution, pointer/manifest/bucket, SQL route settings
- `src/aeat/diagnostics/profile.py`: active-profile resolution, pointer/manifest/bucket
- `src/aeat/domain/buckets/_event_repository.py`: secure-object repository, secure-bound repository
- `src/aeat/domain/filing/_complementaria_repository.py`: secure-object repository, secure-bound repository
- `src/aeat/domain/filing/_repository.py`: secure-bound repository
- `src/aeat/domain/invoices/_repository.py`: secure-object repository, secure-bound repository
- `src/aeat/domain/justificante/_repository.py`: secure-bound repository
- `src/aeat/domain/modelos/_calculation_repository.py`: secure-object repository, secure-bound repository
- `src/aeat/domain/modelos/_filing_repository.py`: secure-object repository, secure-bound repository
- `src/aeat/domain/modelos/_repository.py`: secure-object repository, secure-bound repository
- `src/aeat/domain/modelos/_verification_repository.py`: secure-object repository, secure-bound repository
- `src/aeat/domain/submission/_repository.py`: secure-bound repository
- `src/aeat/domain/transactions/_repository.py`: secure-object repository, secure-bound repository
- `src/aeat/domain/usage_ratios/_service.py`: secure-object repository, secure-bound repository
- `src/aeat/entrypoints/cli/__init__.py`: active-profile resolution, pointer/manifest/bucket, master-key session, SQL route settings
- `src/aeat/entrypoints/cli/_app_live.py`: secure-object repository, active-profile resolution
- `src/aeat/entrypoints/cli/_common.py`: active-profile resolution, pointer/manifest/bucket, SQL route settings
- `src/aeat/entrypoints/cli/_config/__init__.py`: secure-object repository, active-profile resolution, pointer/manifest/bucket, master-key session, SQL route settings, plain-file state
- `src/aeat/entrypoints/cli/_config/_google.py`: secure-object repository, plain-file state, outbound storage provider
- `src/aeat/entrypoints/cli/_config/_profile_census.py`: active-profile resolution, pointer/manifest/bucket
- `src/aeat/entrypoints/cli/_ledger.py`: active-profile resolution
- `src/aeat/entrypoints/cli/_modelo.py`: active-profile resolution, pointer/manifest/bucket, SQL route settings
- `src/aeat/entrypoints/cli/_overview.py`: active-profile resolution

The production index above intentionally excludes tests from the expanded list to keep the operational audit readable. Tests were still scanned mechanically. Their dominant signals were explicit `aeat_database_url` or `AEAT_DATABASE_URL` setup, real `SecureObjectRepository(engine=...)` injection, active-profile overrides, and temporary storage roots. This confirms that test sandboxing is primarily route/engine based today, not a first-class storage runtime profile.

## Vault decision overview

The vault decisions are aligned on the target but not yet fully reconciled in language:

- The newer profile lifecycle decisions make active-profile selection `--profile` or settings override, then `AEAT_ACTIVE_PROFILE`, then the `active-profile` pointer file. `WorkflowState.active_profile` is no longer the authority.
- The later profile identity decisions make the profile id a UUID that is also the bucket id, directory name, keystore scope, active pointer payload, and secure-object key root. Display labels are mutable metadata only.
- The secure-storage hardening decision makes `StorageRuntime` the intended routing/runtime gate for profile-bound secure reads and writes.
- The live IVA wallet binding decision separates storage attachment from calculation binding: profile label resolves to UUID, UUID resolves bucket/session/repository, and calculations consume source observations after that storage binding.
- Older bucket lifecycle docs still mention `active-bucket`, `--bucket`, and `AEAT_ACTIVE_BUCKET`. These are superseded concepts but remain present enough to confuse cleanup execution.

Vault paths reviewed by the completed vault agent included the profile lifecycle ADRs from 2026-05-16 and 2026-05-18, profile state and UUID identity ADRs from 2026-05-21, secure-storage hardening and live IVA wallet binding ADRs from 2026-05-22, user profile backend schema ADRs from 2026-05-07, the corresponding plans, and the 2026-05-26 settings route/env audits.

## Findings

ACTIVE-RUNTIME-001 | HIGH | `StorageRuntime` is present but optional
Only `5` files matched the storage-runtime signal, and only `4` were production. `UserProfileLifecycleRepository` is the strongest current adopter through `inspect_bucket_storage_runtime(...)`; most other repositories still instantiate `SecureObjectRepository()` or inherit it through `SecureBoundRepository`. The runtime therefore cannot yet be treated as the application-wide storage contract.

ACTIVE-RUNTIME-002 | HIGH | Direct `SecureObjectRepository()` construction is the main fragmentation vector
The scanner found `146` secure-object repository signal files, with `53` production files. Repository constructors in workflow, transactions, invoices, modelos, usage ratios, AEAT observation stores, Google OAuth, auth sessions, LLM cache/usage, and repair code default to `SecureObjectRepository()`. Those calls rely on global settings, current engine cache state, and current bucket session rather than receiving a validated runtime.

ACTIVE-RUNTIME-003 | HIGH | CLI owns runtime behavior through root callback logic instead of a backend runtime service
The CLI root callback opens sessions, handles bootstrap exemptions, clears i18n cache after session activation, and blocks selected write verbs against root fallback or explicit routes. This prevents some bad routes, but the authoritative write guard lives in CLI transport code and a manually maintained verb list. Backend callers and tests can still bypass that list.

ACTIVE-RUNTIME-004 | HIGH | Test isolation is not a first-class storage runtime
The scanner found `162` test files with SQL route settings signals. Most real-behavior tests sandbox by setting `aeat_database_url`, `AEAT_DATABASE_URL`, or injecting `SecureObjectRepository(engine=...)`. This is preferable to fakes, but it means tests exercise explicit-route behavior more than active-profile runtime behavior. A sanctioned `StorageRuntime.for_test_profile(...)` or equivalent is missing.

ACTIVE-RUNTIME-005 | MEDIUM | Plain JSONL/file stores remain parallel persistence backends
Production plain-file signals include evidence bundles, ledger evidence, business-operation invoices, inventory ledgers, live verification, live notifications, live expedientes, and snapshot bases. Some may be intended export/cache surfaces, but several carry bucket-scoped tax, evidence, or live AEAT data. They need classification as secure-object migrations, explicit non-secure exceptions, or derived/export-only stores.

ACTIVE-RUNTIME-006 | MEDIUM | Profile lifecycle has two partial authorities
`ProfileRepository` is now the cross-store writer, while manifest scanners remain the plaintext live-profile discovery authority. This is correct, but the split means runtime hardening must not collapse manifest discovery into encrypted storage. The cleanup should define manifest scanning as a read-only discovery adapter and `StorageRuntime` as the secure read/write attachment authority.

ACTIVE-RUNTIME-007 | MEDIUM | Settings route classification and session freshness overlap with repository checks
`Settings` computes the SQL route, `classify_storage_route(...)` classifies it, `StorageRuntime` checks readiness, `SecureObjectRepository` checks route/session on selected methods, and master-key activation checks active bucket id. These checks are directionally consistent but duplicated. The policy should be centralized so all repository operations get the same readiness result and same translated failure.

ACTIVE-RUNTIME-008 | MEDIUM | Namespace ownership remains distributed
Namespace constants are spread across domain, application, adapter, outbound, and repair modules. Repair integrity has heuristics for ownership and classification. A storage runtime centralization pass should not only bind routes; it should also introduce or consume a secure-object namespace registry that states owner, sensitivity class, schema version, bucket scope, object-key grammar, and repair policy.

## Backend cleanup plan

1. Promote `StorageRuntime` from diagnostic model to backend factory.
   Add a small application-facing API that can resolve the active runtime, resolve a named bucket runtime, and produce approved repository factories. The API should return typed readiness failures before any repository opens.

2. Replace direct `SecureObjectRepository()` defaults in domain/application repositories.
   Start with `WorkflowStateRepository`, `TransactionCatalogueRepository`, `InvoiceCatalogueRepository`, modelo repositories, `BucketEventHistoryRepository`, `UsageRatioProfile`, auth session stores, Google OAuth stores, and AEAT observation stores. Constructors can keep injection for tests, but production default should come from runtime, not raw settings.

3. Define a real test runtime profile.
   Tests should be able to create an isolated real bucket profile with a real SQLite database, real `BucketSession`, and real secure-object repository without setting arbitrary `AEAT_DATABASE_URL`. Keep explicit database URL tests only for route-classification and refusal behavior.

4. Move CLI guarded-route policy into runtime/backend policy.
   The CLI should ask the runtime whether a verb requires profile-bound storage and render the backend refusal. The manually maintained root callback verb list should shrink or disappear.

5. Classify direct JSONL/plain-file stores.
   For each production plain-file store, decide one of: migrate to secure objects, mark as export-only derived data, mark as cache with rebuild source, or document accepted plaintext exception. Do not leave sensitive bucket-local JSONL as an implicit third persistence backend.

6. Register secure-object namespaces.
   Add a typed registry for namespace, owner domain, sensitivity class, schema version, bucket scope, object-key grammar, retention, and repair/remediation policy. Repositories should import namespace definitions from that registry instead of declaring local strings.

7. Keep manifest scanning separate and explicit.
   Manifest scans are the correct way to list registered profile labels and statuses without unlocking encrypted storage. Make that an explicit `ProfileDiscovery`/manifest-read service so it does not compete with secure runtime attachment.

8. Add a runtime adoption gate.
   Add a CI or test-surface check that flags new production calls to raw `SecureObjectRepository()` and new route-based test setup outside approved helper modules. The scanner categories in this audit can be converted into that guard.

## Immediate priority order

- First: make `WorkflowStateRepository` and bucket-event history runtime-bound. They are central and currently amplify profile/session drift into many commands.
- Second: move transaction, invoice, modelo, usage-ratio, and AEAT observation repositories to runtime-bound defaults.
- Third: convert CLI profile create/switch/delete custom `override_settings(...)` and master-key spans into named runtime operations while preserving their bootstrap requirements.
- Fourth: migrate or explicitly classify JSONL/plain-file stores.
- Fifth: replace explicit-route-heavy test setup with a real test profile runtime fixture.

## Audit disposition

This audit establishes a mechanical baseline: all `1415` Python files under `src/aeat` were read and categorized. The baseline found `467` files with storage/profile signals and `948` with no signal under the current vocabulary. The production cleanup should treat the `169` production matching files as the active centralisation surface and use the `298` matching test files as the test-sandbox migration surface.

The most important implementation conclusion is simple: the application does not need another narrow repository helper. It needs `StorageRuntime` to become the mandatory orchestration boundary for profile-bound storage, with profile discovery, bucket session, settings route, secure-object repository creation, and test-profile sandboxing all attached to that one runtime contract.
