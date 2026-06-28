---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Storage Hierarchy Namespace Inventory

W15.P33 inventories the secure-storage hierarchy constants that still define persisted data shape: bucket paths, object-key grammar, secure-object namespaces, schema versions, and repair classifications.

## Storage Hierarchy

| Surface | Canonical shape | Registry result |
|---|---|---|
| Bucket root | `<root>/buckets/<bucket_id>/` | `BUCKETS_DIRNAME`, `bucket_root` path definition |
| Bucket DB | `<root>/buckets/<bucket_id>/db/` | `BUCKET_DB_DIRNAME`, `bucket_db` path definition |
| Bucket blobs | `<root>/buckets/<bucket_id>/blobs/` | `BUCKET_BLOBS_DIRNAME`, `bucket_blobs` path definition |
| Bucket audit | `<root>/buckets/<bucket_id>/audit/` | `BUCKET_AUDIT_DIRNAME`, `bucket_audit` path definition |
| Bucket manifest | `<root>/buckets/<bucket_id>/manifest.toml` | `BUCKET_MANIFEST_FILENAME`, `bucket_manifest` path definition |
| Bucket lock | `<root>/buckets/<bucket_id>/.lock` | `BUCKET_LOCK_FILENAME`, `bucket_lock` path definition |
| Keystore | `<root>/keystore/<bucket_id>/` | `KEYSTORE_DIRNAME`, `keystore_bucket` path definition |
| SQL secure objects | `db://secure_objects/<namespace>/<object_key>` | `secure_objects_table` path definition |
| Blob manifest | `<root>/blobs/<sha256[:2]>/<sha256>.manifest.json` | `BLOB_MANIFEST_SCHEMA_VERSION`, `blob_manifest` path definition |

## Application Namespaces Enrolled

| Registry key | Namespace | Sensitivity | Schema | Object-key grammar |
|---|---|---|---:|---|
| `workflow_state` | `aeat.workflow` | FINANCIAL | 1 | `state` |
| `workflow_runs` | `aeat.application.workflow.runs` | FINANCIAL | 1 | `{run_id}` |
| `user_profile_value` | `aeat.application.user_profile.value` | IDENTITY | 1 | `user-profile:{profile_id}` |
| `user_profile_snapshot` | `aeat.application.user_profile.snapshot` | IDENTITY | 1 | `user-profile-snapshot:{profile_id}:{snapshot_id}` |
| `profile_inventory_ledger` | `aeat.persistence.profile.inventory` | FINANCIAL | 1 | `default` |
| `profile_assets_ledger` | `aeat.persistence.profile.assets` | FINANCIAL | 1 | `default` |
| `profile_assets_amortization_ledger` | `aeat.persistence.profile.assets.amortization` | FINANCIAL | 1 | `default` |
| `repair_integrity_decisions` | `aeat.application.repair_integrity.decisions` | AUDIT | 1 | `{decision_id_sha256_hex}` |
| `application_filing_history` | `aeat.application.filing.history` | AUDIT | 1 | `{modelo}` |
| `auth_apoderado_configuration` | `aeat.auth.apoderado` | IDENTITY | 1 | `{bucket_id}` |
| `calculation_observations` | `aeat.calculations.observations` | AUDIT | 1 | `{modelo}:{filing_year}:{period}` |
| `iva_wallet_reconciliation_decisions` | `aeat.calculations.iva_wallet.reconciliation_decisions` | AUDIT | 1 | `iva-wallet-decision:{sha256(...)}` |
| `iva_wallet_reconciliation_decision_events` | `aeat.calculations.iva_wallet.reconciliation_decision_events` | AUDIT | 1 | `iva-wallet-decision-event:{sha256(...)}` |
| `iva_compensation_history` | `aeat.calculations.iva_compensation.history` | AUDIT | 1 | `303:{filing_year}:{period}` |
| `live_iva_remote_state_acquisitions` | `aeat.application.live.iva_remote_state_acquisitions` | AUDIT | 1 | `live-iva-acquisition:{target_year}:{target_period}:{timestamp}:{sha256(...)}` |
| `application_evidence_bundles` | `aeat.application.evidence.bundles` | AUDIT | 1 | `{bundle_id}` |
| `ledger_classification_rules` | `aeat.ledger.classification.rules` | AUDIT | 1 | `{rule_id}` |
| `live_borrador_100_snapshot` | `aeat.application.live.borrador_100_snapshot` | FINANCIAL | 1 | `modelo-100-borrador-snapshot:{bucket_id}:{snapshot_id}` |
| `live_census_snapshot` | `aeat.application.live.census_snapshot` | IDENTITY | 1 | `census-snapshot:{bucket_id}:{snapshot_id}` |
| `live_expedientes_snapshot` | `aeat.application.live.expedientes_snapshot` | FINANCIAL | 1 | `expedientes-snapshot:{bucket_id}:{snapshot_id}` |
| `live_notifications_snapshot` | `aeat.application.live.notifications_snapshot` | FINANCIAL | 1 | `notifications-snapshot:{bucket_id}:{snapshot_id}` |
| `live_verify_observations` | `aeat.application.live.verify_observations` | IDENTITY | 1 | `verify-observation:{bucket_id}:{observation_id}` |
| `aeat_browser_sessions` | `aeat.outbound.aeat.auth.sessions` | SESSION | 1 | `{storage_state_path_posix}` |
| `clave_movil_diagnostics` | `aeat.outbound.aeat.auth.clave_movil.diagnostics` | SESSION | 1 | `{diagnostic_id_or_timestamp_iso}` |
| `google_oauth_client` | `aeat.google.oauth.client` | SECRET | 1 | `{profile}` |
| `google_oauth_token` | `aeat.google.oauth.token` | SECRET | 1 | `{profile}` |
| `google_oauth_metadata` | `aeat.google.oauth.metadata` | FINANCIAL | 1 | `{profile}` |
| `google_drive_config` | `aeat.google.drive.config` | FINANCIAL | 1 | `{profile}` |
| `llm_cache` | `aeat.outbound.llm.cache` | DIAGNOSTIC | 1 | `{logical_root}|{provider}|{model}|{prompt_hash}|{args_hash}` |
| `llm_usage` | `aeat.outbound.llm.usage` | DIAGNOSTIC | 1 | `{logical_root}|{created_at_iso}|{request_id}|{uuid4_hex}` |
| `aeat_filed_declaration_artefacts` | `aeat.outbound.aeat.sede.filed_declaration.artefacts` | FINANCIAL | 1 | `{sha256_hex}` |
| `aeat_filed_declaration_observations` | `aeat.outbound.aeat.sede.filed_declaration.observations` | FINANCIAL | 1 | `{sha256(modelo,ejercicio,period,expediente_id)}` |
| `aeat_iva_wallet_observations` | `aeat.outbound.aeat.sede.iva_compensation_wallet.observations` | FINANCIAL | 1 | `{sha256(taxpayer_nif,target_year,target_period,captured_at)}` |

## Domain And Adapter Namespaces Registered

The registry also records discovered domain and adapter namespaces so later W03/W15 follow-up work can replace remaining local constants without redoing discovery: bucket event history, submission records, justificante metadata, filing drafts, filing amendments, invoice catalogue, transaction catalogue, usage ratios, modelo work-unit/calculation/filing/verification catalogues, attachment blob/manifest namespaces, AEAT browser session state, Clave Movil diagnostics, Google OAuth and Drive configuration, LLM cache and usage telemetry, and AEAT Sede filed-declaration and IVA-wallet observation records.

## Findings

- Prior state duplicated `schema_version = 1`, `"catalogue"`, `"state"`, bucket path segments, and application namespace strings across storage and application modules.
- Several object-key grammars embed bucket identifiers in storage metadata by design: profile snapshots, live snapshots, transaction catalogues, and usage-ratio profiles. These are now explicit registry grammar strings and remain candidates for future privacy review.
- Repair decision listing was using `list_keys`, which returns HMAC lookup digests rather than natural object keys. W15.P33 changed listing to enumerate decrypted records and validate each content-addressed decision id.
- `SecureBoundRepository` now accepts an explicit `bucket_id` route so migrated repositories can bind to a named bucket through the storage runtime instead of relying only on ambient active profile state.
- Outbound storage-provider `_probe` namespaces remain outside this registry because they are provider-side sentinel paths, not encrypted SQL secure-object namespaces. They remain tracked by the remote-mirror/provider-store waves.

## Follow-Up

- Replace remaining domain-level namespace and catalogue constants with the registered domain entries in the W03 namespace-registry wave.
- Add repair-policy ownership metadata through `W03.P06.S26` and registry completeness coverage through `W03.P06.S27`, replacing command-surface heuristics with registry metadata.
- Retire residual literal path assertions in tests by asserting through registry path definitions when those tests are not directly proving filesystem layout.
