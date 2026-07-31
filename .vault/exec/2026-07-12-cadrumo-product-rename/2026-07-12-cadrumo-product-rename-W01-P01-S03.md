---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:ab625404cbdb68df0e10df3f5df98e66951ef87286b7e5afa10b4acba0284453'
step_id: 'S03'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Classify every persistence root, database, namespace, session directory, and bundle suffix

## Scope

- `persistence identity matrix`

## Description

- Re-read the accepted rename ADR, its research, the approved L4 plan, and current `HEAD` before discovery.
- Locate persistence identity authorities with semantic code and vault searches, then confirm every root, filename, namespace, session path, cache, log, telemetry path, and bundle convention with exact searches.
- Classify each surface by referent and define its Cadrumo cutover or AEAT retention behavior without changing production code.
- Record the complete refusal matrix required by the no-compatibility and no-automatic-migration decisions.

## Outcome

### Decision rule

The leading `aeat` in an application path, filename, setting, or logical namespace is product identity and becomes `cadrumo`. An `aeat` segment that names the external tax authority remains `aeat`. Thus `aeat.outbound.aeat.auth.sessions` becomes `cadrumo.outbound.aeat.auth.sessions`: the first segment owns the application namespace; the second names the counterparty. Every product-state change is a hard cut. Cadrumo may detect former state only to refuse it clearly; it must not read, import, move, re-key, delete, or fall back to it.

### Filesystem roots and filenames

| Surface and exact source evidence | Class | Cadrumo disposition | Old-state behavior |
| --- | --- | --- | --- |
| Installed application directory `_APP_DIRNAME = "aeat"`, yielding `%LOCALAPPDATA%/aeat/storage`, `$XDG_DATA_HOME/aeat/storage`, or `~/Library/Application Support/aeat/storage`; `src/aeat/core/_config_state_root.py:63,149-151,195` | Product-owned rename | `_APP_DIRNAME = "cadrumo"`; checkout `var/storage` remains structurally unchanged because its path has no product token | If the sibling former application root exists, report incompatible Cadrumo state and refuse any implicit adoption |
| Central setting `aeat_local_storage_root` and explicit `AEAT_LOCAL_STORAGE_ROOT`; `src/aeat/core/config.py:231-247` | Product-owned rename | `cadrumo_local_storage_root` and `CADRUMO_LOCAL_STORAGE_ROOT` | Do not read the former environment variable or former root |
| Root fallback and bucket database `aeat.db`; `src/aeat/core/config.py:932,939`, `src/aeat/core/_config_storage_route.py:50,126`, `src/aeat/adapters/persistence/storage/master_key/_master_key.py:803` | Product-owned rename | `cadrumo.db` at both `<root>/cadrumo.db` and `<root>/buckets/<id>/db/cadrumo.db` | A former database is incompatible; refuse rather than attach, rename, or migrate it |
| Derived token root `<root>/tokens` exposed as `aeat_token_dir`; `src/aeat/core/config.py:110-121,949-972` | Product-owned rename | `cadrumo_token_dir` / `CADRUMO_TOKEN_DIR`; physical child remains `tokens` | Never consult the former override; old application root is refused |
| Derived secret, blob, and audit roots `secrets`, `blobs`, `audit`; `src/aeat/core/config.py:80-84,1009-1019` | Product-owned rename | Rename fields and environment prefix to Cadrumo; stable generic child names remain | No former setting fallback; no old-root traversal |
| Backup root `var/backups`; `src/aeat/core/config.py:169-172` | Product-owned rename | Rename setting/env identity; retain generic child layout unless later implementation centralizes it under the state root | Refuse automatic discovery or restore from former configured root |
| Product financial roots `var/financial/{transactions,invoices,attachments,purchase-invoice-evidence,ledgers}` and `usage-ratios.json`; `src/aeat/core/_config_integration_fields.py:88-113` | Product-owned rename | Rename all `aeat_*` settings to `cadrumo_*`; retain domain-generic physical names | Do not parse former environment variables or auto-open former roots |
| Registry parity root `var/audit/registry/parity`; `src/aeat/core/_config_integration_fields.py:68-71` | Product-owned rename | Rename setting/env identity; physical taxonomy remains generic | No former override fallback |
| Bucket layout `buckets/<id>/{db,blobs,audit}`, `manifest.toml`, `.lock`, `output-language.hint`, `keystore`, `bucket.dek.json`, `active-profile`, and `master.recovery.key`; `src/aeat/adapters/persistence/storage/_namespace_registry.py:24-32`, `src/aeat/core/_bucket_pointer_io.py:35`, `src/aeat/application/user_profile/_custody.py:40` | Product-owned state, lexically neutral | Retain child spellings under the new Cadrumo root | Never mount the former root; detection is refusal-only |
| Diagnostic log root `<root>/logs`, setting `aeat_log_dir`, and filename `aeat.log`; `src/aeat/core/config.py:340-350,978-1003`, `src/aeat/core/logging.py:85,309-318` | Product-owned rename | `cadrumo_log_dir`, `CADRUMO_LOG_DIR`, and `cadrumo.log` | Do not merge or append to former logs |
| MCP local trajectory root `<root>/telemetry/<session>.jsonl`; `src/aeat/entrypoints/mcp/_telemetry.py:15-25,43,84-86` | Product-owned state, neutral child | Retain `telemetry` below Cadrumo root | Former telemetry is neither read nor promoted |
| Corpus index `<root>/corpus-search/{corpus.sqlite,corpus-vectors.npy,corpus-chunk-ids.json}`; `src/aeat/application/corpus_search/_runtime.py:39-50` | Product-owned rebuildable cache, neutral children | Rebuild below Cadrumo root | Ignore former cache; do not migrate it |
| Search model cache `<root>/search-models`; `src/aeat/application/corpus_search/_query_embed.py:33,45-48` | Product-owned rebuildable cache, neutral child | Re-download/rebuild below Cadrumo root | Ignore former cache |
| Registry pickle `aeat_registry_<hash>.pkl` in configured or platform temp cache; `src/aeat/domain/calculations/registry/_loader.py:1187`, `src/aeat/domain/calculations/registry/_loader_cache.py:129-145` | Product-owned rename | `cadrumo_registry_<hash>.pkl` and renamed cache setting/env | Never load former pickle; leave it untouched for normal expiry/cleanup |
| Observability files `events.jsonl`, `trace.json`, and `envelope.json`; `src/aeat/core/observability/_context.py:48`, `src/aeat/core/observability/_store.py:37-39` | Product-owned state, neutral filenames | Retain filenames only within Cadrumo-owned run roots | Do not ingest former traces as Cadrumo runs |
| LLM logical display roots and encrypted stores `llm-cache`, `llm-usage`, and `llm-run-telemetry`; `src/aeat/core/observability/_fingerprint.py:177-180`, `src/aeat/adapters/outbound/llm/_run_telemetry.py:126` | Product-owned state | Retain generic display children but move logical namespace prefixes to Cadrumo | No old namespace fallback |
| Product LLM directory settings `aeat_llm_cache_dir`, `aeat_llm_usage_dir`, and `aeat_llm_run_telemetry_dir`; `src/aeat/core/config.py:650-662` | Product-owned rename | Rename settings/env identities to Cadrumo; retain generic `var/llm-*` defaults | Never read former overrides or promote former records |
| Submission, workflow, draft, inbox, observability, justificante, and filing-history roots `aeat_submissions_dir`, `aeat_submission_browser_trace_dir`, `aeat_workflow_runs_dir`, `aeat_drafts_dir`, `aeat_inbox_dir`, `aeat_inbox_pdf_dir`, `aeat_runs_dir`, `aeat_justificantes_dir`, and `aeat_filing_history_dir`; `src/aeat/core/config.py:754-786,837-859` | Product-owned rename | Rename settings/env identities to Cadrumo; retain domain-generic physical children | Do not read former overrides or state |
| AEAT status cache and browser-trace settings `aeat_status_cache_dir` and `aeat_status_browser_trace_dir`; `src/aeat/core/config.py:812-832` | Mixed: authority-derived content in product-controlled cache custody | Rename the product control to Cadrumo while retaining AEAT terminology in descriptions and payload semantics | Rebuild; never load the former cache |
| AEAT browser storage state `<aeat_token_dir>/<bucket-id>-storage.json` and metadata/lock material; `src/aeat/adapters/outbound/aeat/browser/_factory.py:184`, `src/aeat/application/auth/_acquisition_lock.py` | Mixed: product-owned directory, authority-owned session payload | Place the unchanged authority session format below the Cadrumo token root | Never resume a session from the former product root; require fresh authentication |
| Bundled authority roots `aeat_manuals_root`, `aeat_normatives_root`, and `aeat_iva_catalogue_root`; `src/aeat/core/config.py:375-396` | Authority-owned retain | Retain AEAT setting names and `registry/aeat` taxonomy; only their Python package path moves in the later root relocation | Continue reading the reviewed bundled authority corpus; this is not old application state |
| Opt-in wallet diagnostic directory `aeat_wallet_diagnostic_dump_dir`; `src/aeat/core/config.py:406-421`, consumed as the caller-selected `dump_dir` by `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py:201,481,573,676-705` | Product-owned rename with authority-owned payload terminology | Rename the local custody control to `cadrumo_wallet_diagnostic_dump_dir` / `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR`; retain AEAT cartera, Sede, and wallet terminology in descriptions and redacted structural payloads | Do not read the former override or auto-ingest its directory; operator explicitly chooses a new Cadrumo-owned destination |
| Google Drive folder default `aeat-vault`; `src/aeat/core/_config_integration_fields.py:43-47` | Product-owned rename | `cadrumo-vault` and Cadrumo setting/env identity | Do not automatically discover, rename, or reuse `aeat-vault` |
| Blob ciphertext `.enc`, blob manifest suffix, profile ledger filenames, evidence `manifest.json`, and corpus manifest/extraction suffixes; storage and evidence modules | Format/domain-owned retain | Retain because none encodes product identity | Normal format validation applies |

### Logical namespace registry

`src/aeat/adapters/persistence/storage/_namespace_registry.py` declares 67 logical namespaces. All 67 namespace strings and all `owner` module strings are product-owned at their leading segment and must move atomically to the Cadrumo package identity. The 61 ordinary production/test entries replace leading `aeat.`, `aeat-test.`, or `aeat-tests.` with `cadrumo.`, `cadrumo-test.`, or `cadrumo-tests.` respectively.

The complete ordinary set is: `WORKFLOW_STATE_NAMESPACE`, `WORKFLOW_RUN_NAMESPACE`, `USER_PROFILE_VALUE_NAMESPACE`, `USER_PROFILE_SNAPSHOT_NAMESPACE`, `PROFILE_INVENTORY_LEDGER_NAMESPACE`, `PROFILE_ASSETS_LEDGER_NAMESPACE`, `PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE`, `PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE`, `PROFILE_PRORRATA_REGISTER_NAMESPACE`, `REPAIR_INTEGRITY_DECISION_NAMESPACE`, `APPLICATION_FILING_HISTORY_NAMESPACE`, `AUTH_APODERADO_CONFIGURATION_NAMESPACE`, `CALCULATION_OBSERVATIONS_NAMESPACE`, `RETENCION_OBSERVATIONS_NAMESPACE`, `WITHHOLDING_OBSERVATIONS_NAMESPACE`, `IVA_WALLET_RECONCILIATION_DECISIONS_NAMESPACE`, `IVA_WALLET_RECONCILIATION_DECISION_EVENTS_NAMESPACE`, `IVA_COMPENSATION_HISTORY_NAMESPACE`, `LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE`, `APPLICATION_EVIDENCE_BUNDLE_NAMESPACE`, `LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE`, `LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE`, `LEDGER_CLASSIFICATION_RULES_NAMESPACE`, `LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE`, `LIVE_M036_DECLARATION_NAMESPACE`, `M145_COMMUNICATION_RECORD_NAMESPACE`, `TEST_SNAPSHOT_BASE_PROBE_NAMESPACE`, `TEST_SESSION_LIFECYCLE_NAMESPACE`, `TEST_SECURE_BOUND_CONTRACT_NAMESPACE`, `TEST_RUNTIME_PROFILE_NAMESPACE`, `LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE`, `LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE`, `LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE`, `LIVE_VERIFY_OBSERVATION_NAMESPACE`, `ATTACHMENT_BLOB_NAMESPACE`, `ATTACHMENT_MANIFEST_NAMESPACE`, `GOOGLE_OAUTH_CLIENT_NAMESPACE`, `GOOGLE_OAUTH_TOKEN_NAMESPACE`, `GOOGLE_OAUTH_METADATA_NAMESPACE`, `GOOGLE_DRIVE_CONFIG_NAMESPACE`, `GOOGLE_CREDENTIAL_SOURCE_NAMESPACE`, `LLM_CACHE_NAMESPACE`, `LLM_USAGE_NAMESPACE`, `LLM_RUN_TELEMETRY_NAMESPACE`, `MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE`, `MODELO_REVIEW_PACKAGE_RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE`, `MODELO_REVIEW_PACKAGE_RECIPIENT_REPLAY_GUARD_NAMESPACE`, `MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE`, `BUCKET_EVENT_HISTORY_NAMESPACE`, `SUBMISSION_RECORDS_NAMESPACE`, `JUSTIFICANTE_METADATA_NAMESPACE`, `FILING_DRAFTS_NAMESPACE`, `FILING_AMENDMENTS_NAMESPACE`, `INVOICE_CATALOGUE_NAMESPACE`, `TRANSACTION_CATALOGUE_NAMESPACE`, `USAGE_RATIO_PROFILE_NAMESPACE`, `MODELO_WORK_UNIT_CATALOGUE_NAMESPACE`, `MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE`, `MODELO_FILING_RECORD_CATALOGUE_NAMESPACE`, `MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE`, and `TRANSACTION_PARTICIPATION_INDEX_NAMESPACE`.

Six mixed authority namespaces retain their internal authority segment while changing the product prefix: `AEAT_BROWSER_SESSION_NAMESPACE` becomes `cadrumo.outbound.aeat.auth.sessions`; `CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE` becomes `cadrumo.outbound.aeat.auth.clave_movil.diagnostics`; `CLAVE_PERMANENTE_DIAGNOSTICS_NAMESPACE` becomes `cadrumo.outbound.aeat.auth.clave_permanente.diagnostics`; `AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE` becomes `cadrumo.outbound.aeat.sede.filed_declaration.artefacts`; `AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE` becomes `cadrumo.outbound.aeat.sede.filed_declaration.observations`; and `AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE` becomes `cadrumo.outbound.aeat.sede.iva_compensation_wallet.observations`. Their constant names may retain `AEAT_` because they describe authority data; their `owner` strings become `cadrumo.adapters.outbound.aeat...`.

No namespace alias table, dual lookup, row-copy migration, or import fallback is allowed. The namespace cut intentionally makes all rows written under former strings incompatible Cadrumo state.

### Bundle suffix and ambiguous surfaces

The test suite documents `.aeat-bucket.tar.gz` as the product bundle convention in `src/aeat/application/bucket_maintenance/tests/test_service_import_export.py`, `src/aeat/adapters/persistence/storage/tests/test_bundle_crash_windows.py`, and `src/aeat/application/user_profile/tests/test_custody_store_matrix.py`. Production `BucketMaintenanceService` accepts caller-selected archive paths and enforces schema/header integrity rather than a suffix, so the suffix is **ambiguous as an enforced contract but product-owned as published identity**. User-facing defaults/examples must become `.cadrumo-bucket.tar.gz`; import must refuse former bundle schema/product identity based on authenticated header metadata, not merely filename. Adding a Cadrumo product marker or changing archive schema requires the later bundle implementation Step; S03 authorizes no automatic old-bundle import.

`aeat_storage_backup_dir`, the financial roots, and `aeat_registry_parity_store_dir` currently default under checkout `PROJECT_ROOT/var` rather than deriving from `aeat_local_storage_root`. They are **product-owned, but placement is ambiguous**: the rename must change their setting/environment identities, while relocating their physical defaults under the installed platform root would be an architectural change not decided here. Preserve placement unless a separate decision authorizes consolidation.

`AEAT_BROWSER_SESSION_NAMESPACE` and files containing authenticated AEAT cookies are **authority-owned payloads inside product-owned custody**. Retain AEAT terminology and payload semantics, change only the enclosing Cadrumo root and leading namespace segment, and require a fresh authority session after cutover.

### Matrix counts

- Product-owned rename: 67 logical namespace prefixes/owners, 1 installed application directory, 1 database filename used in two route shapes, 1 log filename, 1 registry-cache filename prefix, 1 Google Drive vault folder, all product-prefixed persistence settings/environment variables, and the published bucket suffix.
- Product-owned neutral children retained under the new root: 11 bucket-layout names, 3 derived state directories, 2 corpus-search cache directories with 3 cache filenames, the telemetry/log directory labels, and generic observability/blob/evidence filenames.
- Authority-owned retain inside renamed custody: 6 mixed secure namespaces, AEAT browser-session payload semantics, and authority-facing session terminology.
- Ambiguous and resolved by this matrix: 3 checkout-root groups remain in place but rename their settings; `.aeat-bucket.tar.gz` becomes a Cadrumo convention plus authenticated refusal rather than suffix-only validation; authority sessions require fresh acquisition rather than reuse.

## Notes

- Production code was not edited. Discovery was read-only; only this Step Record and the plan checkbox are owned by the Step.
- The worktree contains extensive unrelated concurrent changes. Scoped status and diffs showed no pre-existing change to this Step Record and no pre-existing plan diff before execution.
- The initial broad exact search was noisy because `session` and `cache` are common runtime concepts; the final matrix is grounded in constructors, constants, and the central namespace registry rather than raw occurrence counts.
