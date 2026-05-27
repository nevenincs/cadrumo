---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
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
| `repair_integrity_decisions` | `aeat.application.repair_integrity.decisions` | AUDIT | 1 | `{decision_id_sha256_hex}` |
| `application_filing_history` | `aeat.application.filing.history` | AUDIT | 1 | `{modelo}` |
| `auth_apoderado_configuration` | `aeat.auth.apoderado` | IDENTITY | 1 | `{bucket_id}` |
| `calculation_observations` | `aeat.calculations.observations` | AUDIT | 1 | `{modelo}:{filing_year}:{period}` |
| `iva_wallet_reconciliation_decisions` | `aeat.calculations.iva_wallet.reconciliation_decisions` | AUDIT | 1 | `iva-wallet-decision:{sha256(...)}` |
| `iva_wallet_reconciliation_decision_events` | `aeat.calculations.iva_wallet.reconciliation_decision_events` | AUDIT | 1 | `iva-wallet-decision-event:{sha256(...)}` |
| `iva_compensation_history` | `aeat.calculations.iva_compensation.history` | AUDIT | 1 | `303:{filing_year}:{period}` |
| `ledger_classification_rules` | `aeat.ledger.classification.rules` | AUDIT | 1 | `{rule_id}` |
| `live_borrador_100_snapshot` | `aeat.application.live.borrador_100_snapshot` | FINANCIAL | 1 | `modelo-100-borrador-snapshot:{bucket_id}:{snapshot_id}` |
| `live_census_snapshot` | `aeat.application.live.census_snapshot` | IDENTITY | 1 | `census-snapshot:{bucket_id}:{snapshot_id}` |

## Domain And Adapter Namespaces Registered

The registry also records discovered domain and adapter namespaces so later W03/W15 follow-up work can replace remaining local constants without redoing discovery: bucket event history, submission records, justificante metadata, filing drafts, filing amendments, invoice catalogue, transaction catalogue, usage ratios, modelo work-unit/calculation/filing/verification catalogues, and attachment blob/manifest namespaces.

## Findings

- Prior state duplicated `schema_version = 1`, `"catalogue"`, `"state"`, bucket path segments, and application namespace strings across storage and application modules.
- Several object-key grammars embed bucket identifiers in storage metadata by design: profile snapshots, live snapshots, transaction catalogues, and usage-ratio profiles. These are now explicit registry grammar strings and remain candidates for future privacy review.
- Repair decision listing was using `list_keys`, which returns HMAC lookup digests rather than natural object keys. W15.P33 changed listing to enumerate decrypted records and validate each content-addressed decision id.
- `SecureBoundRepository` now accepts an explicit `bucket_id` route so migrated repositories can bind to a named bucket through the storage runtime instead of relying only on ambient active profile state.

## Follow-Up

- Replace remaining domain-level namespace and catalogue constants with the registered domain entries in the W03 namespace-registry wave.
- Add repair-policy fields to namespace definitions when W03.P06/S41 lands, replacing command-surface heuristics with registry metadata.
- Retire residual literal path assertions in tests by asserting through registry path definitions when those tests are not directly proving filesystem layout.
