---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace google-oauth with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#google-oauth'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-13'
# Complexity tier (mandatory for new plans).
# Allowed: L1 (Steps only), L2 (Phases above Steps),
# L3 (Waves above Phases above Steps), L4 (Epic above Waves
# above Phases above Steps; PM association required).
# Pre-existing plans without this field default to L2.
tier: L2
# Related documents as quoted wiki-links.
# Carries the AUTHORISING documents (ADR, research, reference,
# prior plan) for every Step in this plan; Steps inherit this
# chain; per-row reference footers do not exist.
related:
  - "[[2026-05-08-google-oauth-adr]]"
  - "[[2026-05-12-google-oauth-adr]]"
  - "[[2026-05-13-google-oauth-adr]]"
  - "[[2026-05-13-google-oauth-snapshot-adr]]"
  - "[[2026-05-13-google-oauth-inbound-adr]]"
  - "[[2026-05-13-google-oauth-taxonomy-adr]]"
  - "[[2026-05-13-google-oauth-calc-sheets-adr]]"
  - "[[2026-05-13-google-oauth-twoway-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-06-google-oauth-research]]"
  - "[[2026-05-06-google-oauth-audit]]"
  - "[[2026-05-06-secure-persistence-enforcement-adr]]"
---

# `google-oauth` `Google OAuth integration master plan` plan

Replaces the discarded gcloud-CLI Google Workspace stack with a fresh self-hosted OAuth Desktop application, a provider-agnostic storage abstraction, a per-row continuous mirror to Google Drive at the ciphertext layer, an incoming-bucket ingestion path, per-domain export tiers, calculation-to-Sheets visualisation, and a deferred-but-codified two-way sync verdict. Eight ADRs synthesise into eight phases below; each ADR maps to exactly one phase.

## Proposed Changes

Eight ADRs (ADR-0 through ADR-7) close the architectural surface. The plan walks the implementation in dependency order: authentication foundation first; storage provider abstraction next; sync coordinator and per-bucket semantics; encryption boundary with cross-machine restore via KEK escrow; inbound-bucket ingestion adapter; per-domain substrate hooks; calculation visualisation; two-way sync deferral codification.

The teardown commit `ab952f74` removed the prior stack with no migration shim. Every code path below is fresh; no backwards compatibility surfaces, no deprecation stubs, no partial implementations. Each phase ships complete or its rows stay open.

## Steps

### Phase `P01` - authentication foundation (ADR-0)

Land the OAuth Desktop application surface end-to-end: dependencies, SecureObjectRepository records, CLI commands, refresh lifecycle, typed error hierarchy. The post-teardown `src/aeat/adapters/outbound/google/` scaffold files (`__init__.py`, `_paths.py`, `test_google_auth.py`) are deleted in S00 and replaced by the v1 modules introduced across subsequent steps; no scaffold artifact survives this phase.

- [ ] `P01.S00` - delete the post-teardown scaffold `src/aeat/adapters/outbound/google/__init__.py`, `src/aeat/adapters/outbound/google/_paths.py`, and `src/aeat/adapters/outbound/google/test_google_auth.py`; the package is repopulated by the v1 modules added in S03 (`_records.py`), S05 (`_oauth_flow.py`), S08-S09 (`_refresh.py`), S10 (`_errors.py`), and S14 (`_test_oauth_flow.py`); after S14 a new `__init__.py` exports only the v1 public surface (`OAuthClient`, `OAuthToken`, `OAuthMetadata`, `DriveAppProperties`, `run_login_flow`, `refresh_credentials`, `GoogleAuthError` hierarchy).
- [ ] `P01.S01` - add `google-auth>=2.50.0`, `google-auth-oauthlib>=1.3.1`, `google-api-python-client>=2.195.0` runtime dependencies; `pyproject.toml`.
- [ ] `P01.S02` - introduce top-level `aeat config` Typer sub-app and register the `google` sub-tree under it; `src/aeat/entrypoints/cli/_config.py`.
- [ ] `P01.S03` - implement `DriveAppProperties` pydantic model in the storage adapter namespace and the OAuth client / token / metadata pydantic models in the auth namespace; `src/aeat/adapters/outbound/google/_records.py`.
- [ ] `P01.S04` - implement `aeat config google register --client-json <path> --profile <id>` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P01.S05` - implement `aeat config google login [--profile] [--refresh-only]`; loopback IP + PKCE via `InstalledAppFlow.run_local_server(port=0)`; `src/aeat/adapters/outbound/google/_oauth_flow.py`.
- [ ] `P01.S06` - implement `aeat config google status [--profile] [--format json|text]`; reports profile, account email, granted scopes, last refresh, reauth-required flag.
- [ ] `P01.S07` - implement `aeat config google logout [--profile]`; clears the `oauth-token` and `oauth-metadata` records; preserves `oauth-client`.
- [ ] `P01.S08` - implement lazy refresh with 5-minute clock-skew buffer; re-persist refresh token after every refresh; `src/aeat/adapters/outbound/google/_refresh.py`.
- [ ] `P01.S09` - implement `invalid_grant` detection setting `oauth-metadata.reauth_required=true`; never auto-retry; `src/aeat/adapters/outbound/google/_refresh.py`.
- [ ] `P01.S10` - implement typed `GoogleAuthError` hierarchy (network, client revoked, refresh revoked, expired, scope insufficient, unsecured-mode refused, keychain locked, loopback bind, browser open, client not registered) with structured remediation hints; `src/aeat/adapters/outbound/google/_errors.py`.
- [ ] `P01.S11` - register every `GoogleAuthError` subclass in the project error registry; `src/aeat/core/errors/__init__.py`.
- [ ] `P01.S12` - implement Testing-project 7-day-expiry detection at first refresh and one-time warning; `src/aeat/adapters/outbound/google/_refresh.py`.
- [ ] `P01.S13` - implement unsecured-mode refusal when `aeat_secret_store_backend=unsecured` AND active profile carries a real NIF; `src/aeat/adapters/outbound/google/_oauth_flow.py`.
- [ ] `P01.S14` - write colocated unit tests for OAuth records, login flow, refresh, revocation, error rendering; `src/aeat/adapters/outbound/google/_test_oauth_flow.py`.
- [ ] `P01.S15` - write live tests gated by `AEAT_LIVE_TESTS_ENABLED` against operator-supplied OAuth client; `src/aeat/adapters/outbound/google/_test_oauth_live.py`.
- [ ] `P01.S16` - promote `src/aeat/entrypoints/cli/_config.py` from single-module to package (`src/aeat/entrypoints/cli/_config/__init__.py` re-exporting the existing public surface) so that `_config/_google.py` (and future per-domain sub-CLIs) sit alongside as siblings; preserve every existing import path; no behaviour change; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `P01.S17` - resolve the active `AEAT_PROFILE` at every `aeat config google ...` invocation through the existing `AeatProfile` resolver; raise `ProfileUnboundError` if the env var is unset and no `--profile` override is given; wire the resolver to every OAuth-record load/save path so the per-profile binding in ADR-0 §5 is enforced at one location; `src/aeat/adapters/outbound/google/_profile_binding.py`.
- [ ] `P01.S18` - write a forbidden-import test asserting `src/aeat/adapters/outbound/google/` contains no module named `_oauth_legacy*`, `_gcloud*`, or anything outside the v1 module list from S00; `tests/import_contract/google/test_no_legacy_modules.py`.

### Phase `P02` - storage provider abstraction (ADR-1)

Define `StorageProvider` Protocol and ship both v1 implementations (`LocalFileSystemProvider`, `GoogleDriveProvider`) plus the in-memory test backend.

- [ ] `P02.S01` - define `StorageProvider` Protocol (put / get / delete / iter_namespaces / iter_objects / probe); `src/aeat/adapters/outbound/storage/_protocol.py`.
- [ ] `P02.S02` - define `ProviderObjectMetadata` pydantic record; `src/aeat/adapters/outbound/storage/_records.py`.
- [ ] `P02.S03` - define `ProviderProbeReport` pydantic record with `read_only` mode; `src/aeat/adapters/outbound/storage/_records.py`.
- [ ] `P02.S04` - implement typed `StorageError` hierarchy under `AeatError` (NotFound / Conflict / Permission / Quota / Network / Integrity / Unavailable); `src/aeat/adapters/outbound/storage/_errors.py`.
- [ ] `P02.S05` - register every `StorageError` subclass in the project error registry; `src/aeat/core/errors/__init__.py`.
- [ ] `P02.S06` - implement `LocalFileSystemProvider` against `pathlib`; `src/aeat/adapters/outbound/storage/_local.py`.
- [ ] `P02.S07` - implement `GoogleDriveProvider` against `google-api-python-client`; `src/aeat/adapters/outbound/storage/_google_drive.py`.
- [ ] `P02.S08` - implement `InMemoryDriveProvider` real-implementation test backend; `src/aeat/adapters/outbound/storage/_testing.py`.
- [ ] `P02.S09` - implement `get_storage_provider` factory keyed on `ProviderKind` enum; `src/aeat/adapters/outbound/storage/_factory.py`.
- [ ] `P02.S10` - implement `iter_namespaces` for both backends; `src/aeat/adapters/outbound/storage/_local.py` and `_google_drive.py`.
- [ ] `P02.S11` - implement `iter_objects(namespace)` for both backends; `src/aeat/adapters/outbound/storage/_local.py` and `_google_drive.py`.
- [ ] `P02.S12` - implement `probe(read_only=False)` for both backends with sentinel-file round-trip; `src/aeat/adapters/outbound/storage/_local.py` and `_google_drive.py`.
- [ ] `P02.S13` - write colocated unit tests using `tmp_path` and the in-memory backend; `src/aeat/adapters/outbound/storage/_test_local.py` and `_test_in_memory.py`.
- [ ] `P02.S14` - write live tests gated by `AEAT_LIVE_TESTS_ENABLED` against real Drive; `src/aeat/adapters/outbound/storage/_test_google_drive_live.py`.
- [ ] `P02.S15` - extend `tests/import_contract/test_adr_layout_import_smoke.py` to assert `aeat.adapters.outbound.storage` and its public symbols; `tests/import_contract/test_adr_layout_import_smoke.py`.
- [ ] `P02.S16` - add `aeat_storage_provider_kind` and `aeat_google_drive_root_folder_id` settings to `core/config.py` (pydantic-settings) with strict validation; both settings are per-profile-overridable; `aeat_storage_provider_kind` accepts only the `ProviderKind` enum values; `aeat_google_drive_root_folder_id` is required when kind is `google_drive`; `src/aeat/core/config.py`.
- [ ] `P02.S17` - extend `get_storage_provider` factory to read `aeat_storage_provider_kind` + (when applicable) `aeat_google_drive_root_folder_id`, resolve the active `AEAT_PROFILE`, and instantiate the configured backend with credentials threaded through the P01.S17 profile binding; `src/aeat/adapters/outbound/storage/_factory.py`.
- [ ] `P02.S18` - implement `GoogleDriveProvider` root-folder discovery: create the `aeat-vault/` folder under the operator-configured root folder ID on first probe if absent; reject if the operator-configured root folder ID points to a non-folder file; `src/aeat/adapters/outbound/storage/_google_drive.py`.

### Phase `P03` - drive bucket hierarchy, sync state, conflict resolution (ADR-2)

Land the operator-facing Drive layout and the local sync-state sidecar table; implement the sync coordinator and the refuse-on-conflict semantics.

- [ ] `P03.S01` - add Alembic migration creating `secure_objects_sync_state` table per ADR-2 §5; `migrations/versions/0005_secure_objects_sync_state.py`.
- [ ] `P03.S02` - define `SyncStateRow` pydantic record + `SyncStateStatus` enum; `src/aeat/application/storage/sync/_records.py`.
- [ ] `P03.S03` - implement SQLAlchemy ORM mapping and repository for sync-state rows; `src/aeat/adapters/persistence/storage/sql/_sync_state.py`.
- [ ] `P03.S04` - define `NamespaceLabelDeriver` Protocol; `src/aeat/adapters/outbound/storage/_labels.py`.
- [ ] `P03.S05` - implement label-deriver registry with per-namespace registration API and strict refusal (`UnregisteredNamespaceLabelDeriverError`) at startup when an allow-listed namespace lacks a registered deriver; no silent default, no permissive fallback; `src/aeat/adapters/outbound/storage/_labels.py`.
- [ ] `P03.S06` - implement startup verification that every allow-listed namespace from ADR-5 has a registered label deriver; raise `UnregisteredNamespaceLabelDeriverError` on first storage-provider instantiation if any namespace is unregistered; `src/aeat/adapters/outbound/storage/_labels.py`.
- [ ] `P03.S07` - implement `DriveSync` coordinator full-enumeration algorithm classifying records into unchanged / drift / conflict / fresh / tombstone / ghost / orphan; `src/aeat/application/storage/sync/_coordinator.py`.
- [ ] `P03.S08` - implement `aeat config google sync push` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P03.S09` - implement `aeat config google sync pull` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P03.S10` - implement `aeat config google sync status [--format json|text]` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P03.S11` - implement `aeat config google sync orphans [--format json|text]` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P03.S12` - implement `aeat config google sync claim --file-id <id>` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P03.S13` - implement `--force --resolve {local,remote,fork} --keys <hmac_prefix_list>` conflict-resolution flag matrix; `src/aeat/application/storage/sync/_coordinator.py`.
- [ ] `P03.S14` - implement Drive `appProperties` writes carrying the commit log on every push; `src/aeat/adapters/outbound/storage/_google_drive.py`.
- [ ] `P03.S15` - implement filename surface form `<hmac_prefix_8>--<label>.<ext>` on push; rename detection on label drift; `src/aeat/application/storage/sync/_coordinator.py`.
- [ ] `P03.S16` - write operator-facing `aeat-vault/README.md` content as a string constant and arrange one-time upload on first push; `src/aeat/application/storage/sync/_bucket_readme.py`.
- [ ] `P03.S17` - write colocated unit tests for the diff classifier, conflict refusal, and `--resolve` flags using the in-memory backend; `src/aeat/application/storage/sync/_test_coordinator.py`.
- [ ] `P03.S18` - write live tests gated by `AEAT_LIVE_TESTS_ENABLED` against real Drive for full push / pull / status round-trips; `src/aeat/application/storage/sync/_test_coordinator_live.py`.
- [ ] `P03.S19` - implement underscore-prefixed operator bucket initialization (`_probe/`, `_sync-state/`, `_workspace/`, `_inbound/{pending,processed,rejected}`) on first push if any subfolder is absent; idempotent; emit a `storage.bucket.initialised` log line per created folder; `src/aeat/application/storage/sync/_bucket_init.py`.
- [ ] `P03.S20` - implement `_sync-state/` per-namespace sidecar writer so the local sync-state table is mirrored to Drive on every successful push (one JSON object per namespace, ciphertext-wrapped); `src/aeat/application/storage/sync/_sync_state_mirror.py`.

### Phase `P04` - snapshot encryption boundary and cross-machine restore (ADR-3)

Implement ciphertext-layer mirror (already enforced by ADR-2 wiring), KEK escrow via Argon2id-wrapped passphrase, per-namespace HMAC manifest, and the restore CLI.

- [ ] `P04.S01` - define `KekEscrowEnvelope` pydantic record; `src/aeat/application/storage/snapshot/_records.py`.
- [ ] `P04.S02` - define `NamespaceManifest` and `ManifestEntry` pydantic records; `src/aeat/application/storage/snapshot/_records.py`.
- [ ] `P04.S03` - implement Argon2id KDF over passphrase with configurable params and salt generation; `src/aeat/application/storage/snapshot/_escrow.py`.
- [ ] `P04.S04` - implement KEK wrap via AES-256-GCM under derived wrap key; `src/aeat/application/storage/snapshot/_escrow.py`.
- [ ] `P04.S05` - implement manifest generation with HMAC-SHA256 key derived via HKDF from master KEK; `src/aeat/application/storage/snapshot/_manifest.py`.
- [ ] `P04.S06` - implement `aeat config google escrow create --profile <id>` Typer command prompting for passphrase; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P04.S07` - implement `aeat config google escrow status --profile <id> [--format json|text]` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P04.S08` - implement `aeat config google escrow rotate --profile <id>` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P04.S09` - implement `aeat config google escrow delete --profile <id>` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P04.S10` - implement `aeat config google restore --profile <id> --from-drive [--namespace] [--keys]` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P04.S11` - implement cross-machine bootstrap flow consuming escrow + restoring records into local substrate; `src/aeat/application/storage/snapshot/_restore.py`.
- [ ] `P04.S12` - implement `aeat config google manifest verify --profile <id> [--namespace]` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P04.S13` - regenerate per-namespace manifest on every successful push affecting the namespace; `src/aeat/application/storage/sync/_coordinator.py`.
- [ ] `P04.S14` - write colocated unit tests for KEK wrap / unwrap, manifest HMAC, restore flow against the in-memory backend; `src/aeat/application/storage/snapshot/_test_escrow.py` and `_test_restore.py`.
- [ ] `P04.S15` - write live tests for cross-machine restore against real Drive; `src/aeat/application/storage/snapshot/_test_restore_live.py`.

### Phase `P05` - incoming-bucket ingestion (ADR-4)

Materialise the operator drop-zone semantics: bucket layout, ack via move, triple dedup, validation gates, rejection sidecars.

- [ ] `P05.S01` - add Alembic migration creating `inbound_ingested_files` table; `migrations/versions/0006_inbound_ingested_files.py`.
- [ ] `P05.S02` - implement SQLAlchemy ORM mapping and repository; `src/aeat/adapters/persistence/storage/sql/_inbound_ingested.py`.
- [ ] `P05.S03` - implement filename-convention parser (type / period / source / random); `src/aeat/application/storage/inbound/_filename.py`.
- [ ] `P05.S04` - implement materialise-to-tempfile adapter for Drive-fetched files; `src/aeat/application/storage/inbound/_materialise.py`.
- [ ] `P05.S05` - implement Drive-file-ID dedup layer; `src/aeat/application/storage/inbound/_dedup.py`.
- [ ] `P05.S06` - implement content-hash (md5Checksum) dedup layer; `src/aeat/application/storage/inbound/_dedup.py`.
- [ ] `P05.S07` - implement parse-level dedup composing with existing `application/transactions/_import.py` merge logic; `src/aeat/application/storage/inbound/_dedup.py`.
- [ ] `P05.S08` - implement Stage-1 type detection (MIME + extension + magic bytes); `src/aeat/application/storage/inbound/_validate.py`.
- [ ] `P05.S09` - implement Stage-2 parser-level validation invoking the appropriate inbound provider; `src/aeat/application/storage/inbound/_validate.py`.
- [ ] `P05.S10` - implement move-to-processed acknowledgement; `src/aeat/application/storage/inbound/_acknowledge.py`.
- [ ] `P05.S11` - implement move-to-rejected with sidecar `.error.txt` writer; `src/aeat/application/storage/inbound/_acknowledge.py`.
- [ ] `P05.S12` - implement optional sidecar `<file>.meta.json` parser; `src/aeat/application/storage/inbound/_filename.py`.
- [ ] `P05.S13` - implement `aeat config google sync inbound [--batch] [--dry-run]` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P05.S14` - implement `aeat config google sync inbound --reject --file-id <id>` Typer command for operator manual reject; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P05.S15` - implement `aeat config google sync inbound --replay --file-id <id>` Typer command for operator forced re-ingest; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P05.S16` - write inbound-bucket README content uploaded on first inbound run; `src/aeat/application/storage/inbound/_bucket_readme.py`.
- [ ] `P05.S17` - write colocated unit tests for filename parser, dedup, validation, ack, rejection; `src/aeat/application/storage/inbound/_test_*.py`.
- [ ] `P05.S18` - write live tests for inbound round-trips against real Drive; `src/aeat/application/storage/inbound/_test_inbound_live.py`.
- [ ] `P05.S19` - implement source-kind prefix router registry mapping the four canonical filename prefixes (`purchase-invoice-evidence-`, `payable-invoice-`, `collectible-invoice-`, plus `justificante-`, `bank-statement-`) to their downstream parser handlers; the router refuses any unmapped prefix and any bare `invoice-` prefix per the cli-workflow-redesign invoice-domain-decoupling ADR; `src/aeat/application/storage/inbound/_prefix_router.py`.

### Phase `P06` - per-domain substrate hooks (ADR-5)

Land the substrate amendments and per-domain registrations required by the export taxonomy. Reverse-merge services land as the fully-active v1 backend for the P08 CLI edit and CSV-corrections commands; no settings flag, no inert code, no deferred activation.

- [ ] `P06.S01` - implement `SecureObjectRepository.iter_namespaces()`; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `P06.S02` - implement `SecureObjectRepository.iter_all_records_raw()` returning memory-bounded generator; `src/aeat/adapters/persistence/storage/sql/secure_objects.py`.
- [ ] `P06.S03` - implement `PurchaseInvoiceEvidenceRepository.iter_evidence()`; `src/aeat/domain/purchase_invoice_evidence/_repository.py`.
- [ ] `P06.S03a` - implement `PayableInvoiceRepository.iter_invoices()`; `src/aeat/domain/payable_invoice/_repository.py`.
- [ ] `P06.S03b` - implement `CollectibleInvoiceRepository.iter_invoices()`; `src/aeat/domain/collectible_invoice/_repository.py`.
- [ ] `P06.S05` - implement `application/transactions/_reverse_merge.py` reverse-merge service validating the editable-only field invariant; called by P08 CLI edit and CSV-corrections commands; no settings gate; emits audit row + bucket event on every applied row; `src/aeat/application/transactions/_reverse_merge.py`.
- [ ] `P06.S06` - implement `application/purchase_invoice_evidence/_reverse_merge.py` (notes + attach-to fields editable); called by P08 callers; emits audit + bucket events; `src/aeat/application/purchase_invoice_evidence/_reverse_merge.py`.
- [ ] `P06.S06a` - implement `application/payable_invoice/_reverse_merge.py` (payment_status + notes editable); emits audit + bucket events; `src/aeat/application/payable_invoice/_reverse_merge.py`.
- [ ] `P06.S06b` - implement `application/collectible_invoice/_reverse_merge.py` (payment_status + notes editable); emits audit + bucket events; `src/aeat/application/collectible_invoice/_reverse_merge.py`.
- [ ] `P06.S07` - implement rental-income reverse-merge (amount + dias-alquilados editable); emits audit + bucket events; `src/aeat/application/rental/_reverse_merge_income.py`.
- [ ] `P06.S08` - implement rental-expense reverse-merge (amount + description + allocation-pct editable); emits audit + bucket events; `src/aeat/application/rental/_reverse_merge_expense.py`.
- [ ] `P06.S09` - implement `application/filing/_export_snapshot.py` wrapping `FilingDraftRepository.iter_drafts`; `src/aeat/application/filing/_export_snapshot.py`.
- [ ] `P06.S10` - add Alembic migration introducing `WorkflowResultRepository` table; `migrations/versions/0007_workflow_results.py`.
- [ ] `P06.S11` - implement `WorkflowResultRepository` with `save` / `iter_results` API; `src/aeat/application/workflow/_repository.py`.
- [ ] `P06.S12` - implement `application/deadlines/_export.py::export_schedule(format='json')`; `src/aeat/application/deadlines/_export.py`.
- [ ] `P06.S13` - implement `application/deadlines/_export.py::export_schedule(format='ical')`; `src/aeat/application/deadlines/_export.py`.
- [ ] `P06.S14` - register transactions label deriver; `src/aeat/application/transactions/_label_deriver.py`.
- [ ] `P06.S15` - register purchase-invoice-evidence label deriver; `src/aeat/application/purchase_invoice_evidence/_label_deriver.py`.
- [ ] `P06.S15a` - register payable-invoice label deriver; `src/aeat/application/payable_invoice/_label_deriver.py`.
- [ ] `P06.S15b` - register collectible-invoice label deriver; `src/aeat/application/collectible_invoice/_label_deriver.py`.
- [ ] `P06.S16` - register each rental table label deriver; `src/aeat/application/rental/_label_deriver.py`.
- [ ] `P06.S17` - register filing drafts label deriver; `src/aeat/application/filing/_label_deriver.py`.
- [ ] `P06.S18` - register justificantes label deriver; `src/aeat/application/justificante/_label_deriver.py`.
- [ ] `P06.S19` - register submissions label deriver; `src/aeat/application/filing/_submissions_label_deriver.py`.
- [ ] `P06.S20` - register profile label deriver; `src/aeat/application/profile/_label_deriver.py`.
- [ ] `P06.S21` - register usage-ratios label deriver; `src/aeat/application/usage_ratios/_label_deriver.py`.
- [ ] `P06.S22` - register attachments-manifests label deriver; `src/aeat/application/attachments/_label_deriver.py`.
- [ ] `P06.S23` - register deadlines label deriver; `src/aeat/application/deadlines/_label_deriver.py`.
- [ ] `P06.S24` - register workflow-runs label deriver; `src/aeat/application/workflow/_label_deriver.py`.
- [ ] `P06.S25` - implement `NamespaceAllowList` enforcing the never-export set; `src/aeat/application/storage/sync/_allow_list.py`.
- [ ] `P06.S26` - extend the sensitive-persistence policy test to govern every new substrate hook; `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`.
- [ ] `P06.S27` - write colocated unit tests for each enumeration hook, reverse-merge gate, and label deriver; `src/aeat/<domain>/_test_*.py`.
- [ ] `P06.S28` - define the canonical `SourceKind` enum carrying the four values from the cli-workflow-redesign invoice-domain-decoupling ADR (`ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice`) plus the auxiliary kinds the v1 reverse-merge surfaces consume; every reverse-merge service, label deriver, prefix router, and bucket-event emitter consumes the enum from one location; `src/aeat/domain/source_kind/__init__.py`.
- [ ] `P06.S29` - wire each reverse-merge service to the cli-workflow-redesign bucket-event-history dispatcher; events follow the `ledger.<source-kind>.correction.applied` shape with `source_kind`, `record_id`, `changed_fields`, `operator_actor`, `applied_at` fields; one event per applied row; failure to emit is a hard error, not a swallowed warning; `src/aeat/application/audit/_bucket_event_emitter.py`.
- [ ] `P06.S30` - create the `src/aeat/entrypoints/cli/_app/` package skeleton (`__init__.py` + module-level Typer sub-app) consumed by P08 commands; the package mirrors `_config/` shape: no logic in `__init__.py`, one module per sub-CLI; `src/aeat/entrypoints/cli/_app/__init__.py`.

### Phase `P07` - calculation-to-sheets visualisation (ADR-6)

Land the four-sheet visualisation Spreadsheet per (modelo, period); hybrid formula translation; Spanish UX; protected ranges.

- [ ] `P07.S01` - define `CalcSheetExportPlan` pydantic record + per-sheet layout descriptors; `src/aeat/application/storage/calc_sheets/_records.py`.
- [ ] `P07.S02` - implement the Entradas sheet writer with operator-editable cells + data validation; `src/aeat/application/storage/calc_sheets/_entradas.py`.
- [ ] `P07.S03` - implement the Cálculos sheet writer with hybrid formula translation; `src/aeat/application/storage/calc_sheets/_calculos.py`.
- [ ] `P07.S04` - implement the Resultado sheet writer; `src/aeat/application/storage/calc_sheets/_resultado.py`.
- [ ] `P07.S05` - implement the Procedencia sheet writer with per-casilla audit metadata; `src/aeat/application/storage/calc_sheets/_procedencia.py`.
- [ ] `P07.S06` - implement the Guía de Lectura sheet writer; `src/aeat/application/storage/calc_sheets/_guia.py`.
- [ ] `P07.S07` - implement the hybrid formula translator (mechanical vs static-with-metadata classifier); `src/aeat/application/storage/calc_sheets/_formula_translator.py`.
- [ ] `P07.S08` - implement hidden `_Tariffs` lookup-sheet emitter for bracketed-rate cases; `src/aeat/application/storage/calc_sheets/_lookup_tables.py`.
- [ ] `P07.S09` - implement Spanish-language column headers and labels keyed off existing locale resources; `src/aeat/application/storage/calc_sheets/_locale.py`.
- [ ] `P07.S10` - implement conditional formatting rules (blue input / green calculated / red alert / yellow warning); `src/aeat/application/storage/calc_sheets/_formatting.py`.
- [ ] `P07.S11` - implement `protectedRanges` batchUpdate emission for non-Entradas sheets; `src/aeat/application/storage/calc_sheets/_protection.py`.
- [ ] `P07.S12` - implement cell-note (hover-tooltip) emission for Cálculos cells carrying Oracle + Normativa; `src/aeat/application/storage/calc_sheets/_notes.py`.
- [ ] `P07.S13` - implement `aeat config google sync calc export --modelo --period` Typer command (idempotent); `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P07.S14` - implement `aeat config google sync calc list [--format json|text]` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P07.S15` - implement `aeat config google sync calc delete --modelo --period` Typer command; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P07.S16` - write colocated unit tests for formula translator and per-sheet writers; `src/aeat/application/storage/calc_sheets/_test_*.py`.
- [ ] `P07.S17` - write live tests for calc-sheet exports against real Drive Sheets API gated by `AEAT_LIVE_TESTS_ENABLED`; `src/aeat/application/storage/calc_sheets/_test_calc_live.py`.
- [ ] `P07.S18` - link the calc-sheet formula translator to each Modelo's existing `workbook_parity_refs` so the translated formulas are validated against AEAT-published parity workbooks; a parity-divergence test runs per (modelo, period) in unit tests; `src/aeat/application/storage/calc_sheets/_parity_check.py`.
- [ ] `P07.S19` - factor a dedicated `_sheets_service.py` thin client for the Sheets v4 API distinct from the Drive v3 client; the calc-sheets writers consume only this client; the Drive provider does not import it; `src/aeat/adapters/outbound/google/_sheets_service.py`.

### Phase `P08` - operator-facing CLI edit + CSV-corrections surfaces (ADR-7)

Ship the v1 CLI edit and CSV-corrections commands that operators use to correct editable Tier-1 domain fields. Every command calls the fully-active reverse-merge services from P06; no settings flag, no inert code. CLI surfaces use the EPIC's canonical `aeat app ledger ...` namespaces per the cli-workflow-redesign apex ADR.

- [ ] `P08.S01` - obtain EPIC-team sign-off on the `aeat app ledger transaction edit` single-record correction verb and the `aeat app ledger transaction corrections` sub-namespace; the latter applies symmetrically to `payable-invoice corrections` and `collectible-invoice corrections`; capture the decision under `.vault/exec/2026-05-13-cli-workflow-redesign/`.
- [ ] `P08.S02` - implement `aeat app ledger transaction edit <id> --category --notes` Typer command; `src/aeat/entrypoints/cli/_app/_ledger.py`.
- [ ] `P08.S03` - implement `aeat app ledger payable-invoice edit <id> --payment-status --notes` Typer command; `src/aeat/entrypoints/cli/_app/_ledger.py`.
- [ ] `P08.S04` - implement `aeat app ledger collectible-invoice edit <id> --payment-status --notes` Typer command; `src/aeat/entrypoints/cli/_app/_ledger.py`.
- [ ] `P08.S05` - implement `aeat app ledger rental income edit <id> --amount --dias-alquilados` Typer command; `src/aeat/entrypoints/cli/_app/_ledger.py`.
- [ ] `P08.S06` - implement `aeat app ledger rental expense edit <id> --amount --description --allocation-pct` Typer command; `src/aeat/entrypoints/cli/_app/_ledger.py`.
- [ ] `P08.S07` - implement `aeat app ledger transaction corrections export-csv --period --output` Typer command; `src/aeat/entrypoints/cli/_app/_ledger.py`.
- [ ] `P08.S08` - implement `aeat app ledger transaction corrections import-csv --input [--dry-run]` Typer command with full-validation-before-commit semantics; `src/aeat/entrypoints/cli/_app/_ledger.py`.
- [ ] `P08.S09` - implement `aeat app ledger payable-invoice corrections export-csv` / `import-csv` Typer commands; `src/aeat/entrypoints/cli/_app/_ledger.py`.
- [ ] `P08.S10` - implement `aeat app ledger collectible-invoice corrections export-csv` / `import-csv` Typer commands; `src/aeat/entrypoints/cli/_app/_ledger.py`.
- [ ] `P08.S11` - implement audit logging on every CSV import row emitting both a `reverse_merge_audit` row and a `ledger.<source-kind>.correction.applied` bucket event per the cli-workflow-redesign bucket-event-history ADR; `src/aeat/application/audit/_reverse_merge_audit.py`.
- [ ] `P08.S12` - document the four safety properties and the future-amendment surface in a contributor-facing README under the audit subpackage; `src/aeat/application/audit/README.md`.
- [ ] `P08.S13` - write colocated unit tests for edit commands and CSV round-trips; `src/aeat/entrypoints/cli/_app/_test_ledger_*.py`.
- [ ] `P08.S14` - write a forbidden-import test asserting no `sync pull --workspace-edits` (or any Sheets-pull) verb is registered under `aeat config google sync` in v1; the test introspects the Typer command tree and fails if any matching command exists; defends ADR-7's deferral invariant against future drift; `tests/import_contract/google/test_no_sheets_pull_verb.py`.
- [ ] `P08.S15` - add Spanish CLI localisation strings for every new `aeat config google ...` and `aeat app ledger ...` command (help text, prompts, error messages) keyed off the existing `_i18n` resource module; coverage test asserts no untranslated key for any new command; `src/aeat/entrypoints/cli/_i18n/google.po` + `tests/entrypoints/cli/test_i18n_coverage.py`.

## Parallelization

P01 is the foundation; nothing in P02 onwards can proceed without authenticated access to Drive. P02 must precede P03 / P04 / P05 / P07. P06 can begin in parallel with P02 (operates on local substrate hooks; no Drive dependency). P03 must precede P04 and P05 (sync coordinator is the dependency). P07 depends on both P02 and the registry-side enumeration hooks landed in P06. P08 can begin in parallel with P06 (operates on CLI surfaces; depends only on the per-domain hooks from P06).

Default sequencing:

1. P01 (alone).
2. P02 and P06 in parallel.
3. P03 (depends on P02 finalised).
4. P04 and P05 in parallel (both depend on P03).
5. P07 (depends on P02 and P06 finalised).
6. P08 (depends on P06 finalised).

Within a Phase, Steps are sequenced by file dependency; reviewer judgement on each pair.

## Verification

The plan is complete when every Step is closed `[x]` and the following acceptance checks pass.

- `uv run ty check src/` reports zero errors across all new code.
- `uv run pytest -m unit` passes with new colocated unit tests green.
- `uv run pytest -m live_read` passes when `AEAT_LIVE_TESTS_ENABLED=true` with operator-supplied OAuth client; live tests skip cleanly otherwise.
- `uv run vaultspec-core vault check all` reports zero issues for every ADR in the `google-oauth` feature and this plan.
- `tests/import_contract/test_adr_layout_import_smoke.py` asserts every newly introduced subpackage and public symbol per the ADR-1 / ADR-5 promises; the test passes.
- `tests/import_contract/application/setup/test_cli.py` reflects the new `aeat config google` Typer surface; the test passes.
- `aeat config google status --profile default --format json` returns a valid `ProviderProbeReport` shape after the operator registers a Cloud Console Desktop client + completes `login`.
- `aeat config google sync push --dry-run --profile default` reports the per-namespace diff classifier output (orphans + ghosts + drift + conflicts + unchanged) without writing.
- `aeat config google escrow create --profile default` round-trips against `aeat config google restore --profile default --from-drive` on a fresh workstation with only the passphrase.
- `aeat config google sync calc export --modelo 130 --period 2026Q1` produces a Spreadsheet under `/aeat-vault/_workspace/calc-modelo-130-2026Q1.gsheet` with the documented four-sheet structure, Spanish labels, and `protectedRanges` on every non-Entradas sheet.
- `aeat app ledger transaction edit <id> --category <cat>` updates the substrate row through the existing typed-validation path; the next `aeat config google sync push` reflects the change in Drive.
- The sensitive-persistence policy test continues to pass with every new substrate hook governed.
- No `aeat_enable_two_way_sync` settings flag exists in v1. The reverse-merge service is the unconditional v1 backend for `aeat app ledger <kind> edit` and CSV-corrections import; a future Sheets-pull entry-point would add a new CLI command via its own ADR amendment, not a flag flip.
- `tests/import_contract/google/test_no_sheets_pull_verb.py` (P08.S14) asserts the Typer command tree contains no Sheets-pull verb under `aeat config google sync`; the test passes.
- `tests/import_contract/google/test_no_legacy_modules.py` (P01.S18) asserts no legacy `_gcloud*` / `_oauth_legacy*` modules survive under `src/aeat/adapters/outbound/google/`; the test passes.
- Every new CLI command registered under `aeat config google ...` and `aeat app ledger ...` has Spanish translations covered by `tests/entrypoints/cli/test_i18n_coverage.py`; the test passes.
- The `SourceKind` enum (P06.S28) is the single source-kind registry; a structural test asserts every reverse-merge service, label deriver, prefix router, and bucket-event emitter imports its source-kind value from one location.
- Every reverse-merge service emits a `ledger.<source-kind>.correction.applied` bucket event per applied row; a unit test asserts emission failure surfaces as a hard error, not a silent swallow.
- The `aeat-vault/` Drive folder is created under `aeat_google_drive_root_folder_id` on first probe and the four underscore-prefixed operator buckets (`_probe/`, `_sync-state/`, `_workspace/`, `_inbound/{pending,processed,rejected}`) materialise on first push; idempotent on re-run.
