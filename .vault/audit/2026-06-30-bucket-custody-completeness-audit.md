---
tags:
  - '#audit'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-08'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
  - "[[2026-06-30-bucket-custody-completeness-adr]]"
  - "[[2026-06-30-bucket-custody-completeness-research]]"
---

# `bucket-custody-completeness` audit: `P01 registry custody disposition review`

## Scope

Reviewed the P01 registry implementation against the accepted custody ADR,
supporting research, and the P01 plan rows. The audited patch adds custody
disposition authority to the secure-object namespace registry, exposes the new
types through the storage package API, and extends the registry tests.
The final review scope also includes the SQL secure-object split test support
that needed the new required field in its local registry fixture.

## Findings

The initial review found the P01 dispositions conservative for the
split-custody contract. Structured custody includes cross-period calculation
inputs and structured profile/history stores. Full custody adds evidence, live
snapshots, and audit-history stores. Derived and process-local namespaces are
excluded from both carried profiles.

## Recommendations

Continue with P02 through P06 before treating custody completeness as complete.
The remaining load-bearing work is the payload schema bump, fail-closed coverage
manifest, repository save-path re-encryption on import, and non-tautological
roundtrip tests over populated stores.

## Final Review Addendum

- [x] HIGH - `ledger_business_operation_invoices` was classified as full-only, so structured export/import would have dropped typed payable/collectible invoice catalogues. The namespace was declared `FULL_CUSTODY_ONLY` in `src/aeat/adapters/persistence/storage/_namespace_registry.py`, but the owning repository persists slim pydantic `BusinessOperationInvoiceDocument` records with `source_kind`, amounts, and invoice metadata, not attachment bytes or live snapshots. Those records are calculation inputs: the invoice resolver loads `BusinessOperationInvoiceRepository` and emits binding source observations from `invoice.taxable_base` and `invoice.source_kind`. Because `StorageHierarchyRegistry.namespaces_for_custody_profile(StorageCustodyProfile.STRUCTURED)` includes only `STRUCTURED_CUSTODY`, the classification excluded those durable structured invoice catalogues from the structured custody profile. The ADR only forbids attachment bytes and byte-bearing live snapshots in the cleartext transport; it does not justify dropping structured invoice catalogues while existing structured financial categories still travel. Resolved by reclassifying the namespace as `STRUCTURED_CUSTODY` and asserting that it appears in both custody profiles.

## P02 Review Addendum

- [x] HIGH - Sealed import originally validated `bundle_schema_version` too late. A schema-2 bundle inside a current sealed archive could be decrypted and parsed, then reach filing-baseline validation and potentially bucket provisioning before `deserialize_profile_bundle` rejected it through `SUPPORTED_BUNDLE_SCHEMA_VERSIONS`. Resolved by adding a `BucketMaintenanceService.import_` gate immediately after `UserProfilePortableExport.model_validate_json`, before baseline validation or `_provision_imported_bucket`, and by adding a service regression archive with a valid schema-2 inner bundle that proves no bucket pointer is created.
- [x] MEDIUM - Initial carried-object schema used JSON text for payloads, which would not carry full-custody attachment bytes or arbitrary secure-object payloads. Resolved by carrying canonical base64 payload bytes and the stored 32-byte HMAC lookup digest in `CarriedSecureObject`, matching the secure-object substrate replay requirements.
- [x] MEDIUM - Initial `CoverageManifest` row-count storage was shallow-mutable despite the frozen model config. Resolved by freezing validated row counts with `MappingProxyType` and asserting both default and populated manifests reject in-place mutation.
- [x] REVIEW NOTE - The real CLI profile export/import integration file transiently raised `MemoryError` during legal-corpus normalisation in calculation-registry validation. The isolated failing node then passed, and the exact full-file command passed on rerun. This remains a resource-pressure observation, not a P02 code defect.

## Execution Closeout (P03 - P07)

- [x] CRITICAL (corrects the P02 MEDIUM digest decision) - The P02 `CarriedSecureObject` addressed each carried row by its stored HMAC lookup digest. That digest is keyed by the per-bucket data-encryption key (`HashedLookup._derive_lookup_key` derives the HMAC sub-key from `get_active_master_key`, the active bucket DEK), so a source-bucket digest does not match the digest a fresh-DEK recipient bucket computes for the same natural key, and every point-load (catalogues, observations, attachments, snapshots) would return `None` after a recovery import. Proven empirically with a two-bucket probe (distinct DEKs -> distinct digests -> `save_with_raw_key` row unreadable by natural-key load). Resolved by carrying each row by its **natural** object key and re-saving through the raw substrate `save` on import, which re-digests under the recipient DEK and re-encrypts. The proof is durable in `test_custody_roundtrip.py` and `test_custody_completeness.py` (evidence bytes and the audit trail survive an export -> fresh-root import).

- [x] DONE - Serialise (`serialize_carried_objects`) carries every carried-disposition namespace via a registry-driven natural-key resolver registry; restore (`restore_carried_objects`) re-saves through the substrate and `deserialize_profile_bundle` rebuilds the derived participation index. Resolvers cover all 36 carried namespaces (byte stores, `SecureBoundRepository`, `SecureSnapshotRepository`, single-document catalogues via a fixed-key fallback, and the AEAT filed-declaration stores via extracted module-level key functions). A build-time gate (`test_every_carried_namespace_has_a_natural_key_resolver`) fails closed if a new carried namespace lacks a resolver.

- [x] DONE - Transports split per the ADR: the sealed recovery archive exports under the FULL custody profile (AEAD-encrypted, fail-closed coverage gate); the cleartext bundle stays structured-only and its sensitivity notice now states it is not a full backup. Proven: `test_structured_profile_excludes_attachment_evidence_bytes`.

- [x] DONE - `repair_integrity_decisions` reclassified `STRUCTURED_CUSTODY` -> `PROCESS_LOCAL`: host-local storage-repair decisions are not portable bucket data.

- [x] RESOLVED (test depth, was an honest limitation) - Every carried store is now individually seeded-and-roundtripped, not just the representative patterns. `test_custody_store_matrix.py` seeds one valid row in all 31 generically-carried stores (the live snapshots, retencion/withholding observations, AEAT filed-declaration observations + artefacts + iva-wallet observations, single-document ledgers, invoice/verification catalogues, evidence bundles, submissions, drafts and amendments, m036, verify, profile snapshot, calculation/IVA observations), exports a sealed recovery archive, imports it into a fresh storage root that re-provisions the same bucket id under a new DEK, and reads each store back through its owning repository. Combined with the headline `test_custody_roundtrip` (attachments x2, event history, justificante metadata) and the decision-events check, all 36 carried namespaces are persistence-verified across the recovery boundary. A correctness subtlety surfaced and was handled: bucket-local snapshot stores embed the bucket id in their object key, so the matrix uses same-id fresh-DEK recovery (the real scenario), not two distinct bucket ids.

## Direct-Source Hardening Addendum

- [x] RESOLVED - A follow-up review enforced the user correction "no reexports; provision from real sources" across the bucket custody transport surface. Package-facade imports in `src/aeat/application/user_profile/_bundle.py`, `src/aeat/application/user_profile/_custody_carry.py`, `src/aeat/application/bucket_maintenance/_service.py`, `src/aeat/entrypoints/cli/_config/_profile_bundle.py`, and focused custody/profile tests were replaced with defining modules. A RAG-grounded reviewer reported no blocking issues. Verification: direct-source import scan clean, ruff passed, 59 focused custody/application tests passed, 6 CLI profile export/import integration tests passed, and diff whitespace check passed.

- [x] RESOLVED - Plan closure traceability was repaired after detecting that P03 through P07 were checked in the plan while only P01/P02 exec records existed locally. `vaultspec-core vault add exec --all-steps` scaffolded the missing P03.S07 through P07.S19 records, and each record now carries the executed scope, outcome, and verification notes.

## Adversarial Review Fixes (post-completion, independently confirmed)

A fresh adversarial code review over the whole custody surface (and a parallel
self-probe) found and drove to a fix five issues the passing suite had missed
because it only seeded carried stores and never populated the manifest, the
participation index, or any process-local store:

- [x] CRITICAL - Full-custody coverage gate failed closed on any populated
  PROCESS_LOCAL (workflow/credential) or DERIVED_REBUILDABLE (participation
  index) namespace, so the sealed recovery export would refuse essentially every
  real bucket that had run a calculation. Proven with a two-probe. Fixed: every
  registered namespace declares a disposition and is accounted for; the gate now
  fails closed only on a populated namespace that is not in the registry at all.
  Regression: `test_full_export_tolerates_populated_process_local_namespace` and
  the matrix now also populates a process-local store end to end.
- [x] CRITICAL - The attachment-manifest resolver parsed `Envelope[Attachment]`,
  but the manifest store strips `attachment_id` from the persisted payload
  (re-injected on load), so the resolver raised at export time on any bucket with
  an attached document + manifest. Fixed to recover the natural key from the
  retained content-addressed `sha256` (which the model enforces equal to
  `attachment_id`). Proven by seeding a manifest in `test_custody_roundtrip`.
- [x] MEDIUM - Import provisioned `bundle.profile.profile_id` but restored under
  `header.bucket_id` with no equality check; a divergent/hand-built archive would
  write bucket-local keys under a stale id. Added a fail-closed assertion that the
  two are equal (recovery is same-id only; no cross-id remap exists).
- [x] LOW - A resolver fault surfaced as a bare pydantic error out of the export;
  wrapped resolver invocation to raise a typed `ProfileExportError` naming the
  namespace, and attached the original error detail to the import payload-invalid
  context.
- [x] JUDGEMENT - `aeat.auth.apoderado` (durable per-bucket apoderamiento setup)
  was PROCESS_LOCAL and thus dropped on recovery; reclassified to
  FULL_CUSTODY_ONLY with a resolver and a matrix case. `aeat.google.drive.config`
  stays PROCESS_LOCAL (an OAuth-dependent host integration binding, useless
  without the host-local token).

After these fixes all 37 carried namespaces round-trip through the real recovery
transport and the full custody suite (64 tests) is green.
