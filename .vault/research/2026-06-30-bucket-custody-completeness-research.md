---
tags:
  - '#research'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - '[[2026-06-30-agent-harness-research]]'
  - '[[2026-06-30-agent-harness-adr]]'
  - '[[2026-05-27-profile-portability-adr]]'
  - '[[2026-06-03-bucket-sealed-archive-adr]]'
  - '[[2026-06-03-cli-workflow-redesign-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
---

# `bucket-custody-completeness` research: `per-bucket data-custody completeness`

## Context and motivation

The `agent-harness` feature (research/ADR/plan dated 2026-06-30) names "data
custody & recovery" a first-class operator workflow an LLM tax-advisor agent
must be able to execute, and it treats the per-bucket export/import + sealed
recovery-archive backbone as a stable parent it merely *consumes* (the harness
"adds knowledge and orchestration on top; it does not recompute or restate what
the deterministic layer owns"). The harness assumes the custody backbone is
solid.

It is not. Both export/import transports silently drop most durable per-bucket
state. A "restore" therefore returns a structurally-incomplete profile: missing
evidence bytes, a missing audit trail, and — most dangerously — missing
cross-period calculation inputs that silently corrupt future-period
calculations after the restore. The gap is a correctness and legal-grounding
hole and is currently uncovered by any test. This document grounds the gap with
file:line evidence and frames the four open decisions an ADR must settle. No
implementation is proposed here.

## The shared partial-payload builder

Both custody transports funnel through one payload builder,
`serialize_profile_bundle` (`src/aeat/application/user_profile/_bundle.py:47-88`),
which walks exactly five categories — profile, `work_units`,
`ledger_transactions`, `calculation_revisions`, `filing_records` — and
`deserialize_profile_bundle` (`_bundle.py:96-187`) re-saves only those five.
The payload model `UserProfilePortableExport`
(`src/aeat/domain/user_profile/_portable_export.py:28-66`) has **no field** for
any other durable store. Both transports inherit the builder's blind spots:

- **Cleartext CLI path** — `aeat config profile export` / `import`
  (`src/aeat/entrypoints/cli/_config/_profile_bundle.py`) writes the bundle as
  plaintext JSON on operator disk.
- **Sealed recovery-archive path** — `BucketMaintenanceService.export` /
  `import_` (`src/aeat/application/bucket_maintenance/_service.py:285-487`)
  wraps the **same** bundle in AEAD under a recovery passphrase (built at
  `_service.py:325`, serialised at `:353`). The archive header carries a
  `manifest_digest` that asserts integrity over a bucket manifest whose secure
  objects are not in the payload — a partial backup that presents as a full
  sealed archive (see "Open decision 3").

## The canonical namespace registry is the design lever

There is a single typed registry of every secure-object namespace:
`STORAGE_NAMESPACE_REGISTRY`
(`src/aeat/adapters/persistence/storage/_namespace_registry.py:865`), a tuple
of `SecureObjectNamespaceDefinition` records (`_namespace_registry.py:62-77`).
Each definition carries a `scope: StorageNamespaceScope` field
(`_namespace_registry.py:37-42`) with three members: `PROFILE_LOCAL`,
`BUCKET_LOCAL`, `PROCESS_LOCAL`. `BUCKET_LOCAL` grammars embed `{bucket_id}` in
the object key; `PROFILE_LOCAL` keys do not.

This `scope` field authoritatively partitions the dropped stores into the two
import strategies a design needs, and the live-DB enumeration the `browse` verb
already performs (`SecureObjectRepository.list_namespaces()` at
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:358`, consumed at
`_service.py:273-281` into `BucketNamespaceInventoryRow` rows with per-namespace
row counts) is the natural basis for a completeness/coverage gate. The transport
sees none of this today; `browse` sees every stored namespace at runtime while
the export/import payload carries five.

## Inventory of silently-dropped durable stores

All of the following live in the encrypted secure-object store and are
referenced by **none** of `_bundle.py`. Scope and sensitivity are quoted from
`_namespace_registry.py`.

### CRITICAL

- **Attachment / evidence BYTES + manifests.** Namespaces
  `aeat.domain.attachments.blobs` (`_namespace_registry.py:536-544`, scope
  `PROFILE_LOCAL`, grammar `{sha256_hex}`, FINANCIAL) and
  `aeat.domain.attachments.manifests` (`:545-553`). `AttachmentStore`
  (`src/aeat/adapters/persistence/storage/attachment.py:175`) writes bytes via
  `put_bytes` (`:202`) / `put_file` (`:221`), reads via `read_bytes` (`:251`),
  writes manifests via `write_manifest` (`:276`), iterates via `iter_manifests`
  (`:325`). Transactions and revisions reference evidence by id **only**
  (`Transaction.attachment_ids` / `purchase_invoice_evidence_id` at
  `src/aeat/domain/transactions/_models.py:819-820`; `LedgerEvidenceRow` at
  `src/aeat/domain/modelos/_ledger_filing_snapshot.py:171-173`). On restore
  those ids resolve to nothing → `AttachmentNotFoundError`. This breaks the
  `ledger-evidence-bytes-not-links` and `ledger-derived-revisions-bundle-evidence`
  rules. **Key leverage:** an attachment id *is* the SHA-256 of its bytes
  (`put_bytes` returns the digest, `attachment.py:202-219`), so carrying the
  bytes and `put_bytes`-on-import reproduces the same id — no id rewriting.

- **Filed-revision / calculation observations.** Namespace
  `aeat.calculations.observations` (`_namespace_registry.py:310-318`, scope
  `PROFILE_LOCAL`, grammar `{modelo}:{filing_year}:{period}`, AUDIT).
  `CalculationObservationRepository`
  (`src/aeat/application/calculations/_observations_repository.py:271`) with
  `save_observation` (`:314`) / `load_observation` (`:305`); written by
  `persist_filed_calculation_observation`
  (`src/aeat/application/live/_filed_observation_persistence.py:111-136`).
  Payload `_ObservationEnvelopePayload` wrapping `RegistryModeloObservation`
  with `stamped_revision_id`. These are the cross-period 303 carry-forward
  inputs; orphaning them silently corrupts future-period calculations.

- **IVA compensation history.** Namespace
  `aeat.calculations.iva_compensation.history` (`_namespace_registry.py:369-377`,
  scope `PROFILE_LOCAL`, AUDIT). `IvaCompensationHistoryRepository`
  (`src/aeat/application/calculations/_iva_compensation_history.py:151`) with
  `save_period` (`:179`) / `load_period` (`:169`). Payload
  `IvaCompensationPeriodState`. Cross-period 303 carry input.

- **IVA-wallet reconciliation decisions.** Namespaces
  `aeat.calculations.iva_wallet.reconciliation_decisions`
  (`_namespace_registry.py:351-359`, `PROFILE_LOCAL`, AUDIT) and its immutable
  event store `...reconciliation_decision_events` (`:360-368`).
  `IvaWalletDecisionRepository`
  (`src/aeat/application/calculations/_observations_repository.py:370`) with
  `save_decision` (`:392`) / `load_decision` (`:411`) /
  `load_decision_history` (`:438`). Payload wrapping
  `IvaCompensationReconciliationDecision`. Cross-period reconciliation input.

### HIGH

- **Censo snapshots.** Namespace `aeat.application.live.censo_snapshot`
  (`_namespace_registry.py:434-442`, scope **`BUCKET_LOCAL`**, grammar
  `censo-snapshot:{bucket_id}:{snapshot_id}`, IDENTITY).
  `CensoSnapshotRepository` (`src/aeat/application/live/_censo.py:167`), object
  key `censo_snapshot_object_key` (`_censo.py:133`, embeds `bucket_id` at
  `:141`). Payload `CensoSnapshot`. Bucket-local: the key embeds `{bucket_id}`.

- **Justificante capture snapshots (AEAT-signed receipt PDFs).** Namespace
  `aeat.application.live.justificante_capture_snapshot`
  (`_namespace_registry.py:518-526`, scope **`BUCKET_LOCAL`**, FINANCIAL).
  `JustificanteCaptureSnapshotRepository`
  (`src/aeat/application/live/_justificante.py:256`), `save` (`:308`) enforces a
  bucket-match guard (`:309-313`). Payload `JustificanteCaptureSnapshot`. The
  AEAT-signed receipts are held only here.

- **Bucket event-history audit trail.** Namespace
  `aeat.domain.buckets.event_history` (`_namespace_registry.py:654-663`, scope
  `PROFILE_LOCAL`, single fixed key `catalogue`, FINANCIAL).
  `BucketEventHistoryRepository`
  (`src/aeat/domain/buckets/_event_repository.py:33`) stores the whole history
  as one `BucketEventHistoryCatalogue` blob; `append_bucket_event` (`:138`) is
  idempotent (`mapping[event.event_id] = event`). The entire operator audit
  trail is dropped on export.

### MEDIUM (re-pullable, but lost)

- **Notifications snapshot** `aeat.application.live.notifications_snapshot`
  (`_namespace_registry.py:509-517`, `BUCKET_LOCAL`, FINANCIAL).
- **Expedientes snapshot** `aeat.application.live.expedientes_snapshot`
  (`_namespace_registry.py:500-508`, `BUCKET_LOCAL`, FINANCIAL).
- **Justificante metadata** `aeat.domain.justificante.metadata`
  (`_namespace_registry.py:673-681`, `PROFILE_LOCAL`, AUDIT;
  `JustificanteRepository` at `src/aeat/domain/justificante/_repository.py:31`).
- Related dropped AEAT-outbound stores:
  `AEAT_FILED_DECLARATION_ARTEFACTS_NAMESPACE` (`:626-634`, justificante PDF
  bytes), `AEAT_FILED_DECLARATION_OBSERVATIONS_NAMESPACE` (`:635-643`),
  `AEAT_IVA_WALLET_OBSERVATIONS_NAMESPACE` (`:644-652`),
  `LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE` (`:378-388`).

### EXCLUDE (correct to drop — rebuildable read-cache)

- **Transaction↔revision participation index.** Namespace
  `aeat.domain.modelos.participation_index`
  (`src/aeat/domain/modelos/_participation_index.py:52`). It is a derived,
  self-describing read-side cache; authoritative source is the
  `CalculationRevisionCatalogue` (governed by the
  `ledger-participation-index-is-derived-rebuildable` rule). Rebuild entrypoint
  `rebuild_participation_index` (`src/aeat/application/modelo/_participation_index_rebuild.py:92`).
  The design rebuilds this after import rather than transporting it.

## Bucket-local re-keying is a non-issue for the recovery workflow

The `BUCKET_LOCAL` stores (censo, justificante-capture, notifications,
expedientes) embed `{bucket_id}` in their object keys, and justificante-capture
additionally guards `snapshot.bucket_id == repo bucket` on save
(`_justificante.py:309-313`). This looks like it forces key/payload rewriting on
import. It does not, for the actual recovery workflow: `import_` restores under
`header.bucket_id` (`_service.py:415-467`) — the **same** bucket id the archive
was exported from — provisioning a fresh bucket with a fresh DEK but the same
id. Object keys (which embed the bucket id, not the DEK) are therefore
unchanged; re-saving the typed snapshot payloads under the restored bucket
session reproduces the same keys and the bucket-match guard passes. Per-object
re-encryption still happens (new DEK), exactly as the four structured
categories already do. Re-homing a bucket to a *different* id would require key
rewriting and is out of scope.

## D2 means re-encrypt, not drop — the new ADR extends D1, not contradicts D2

The decision often cited as the reason evidence is absent is "D2 — strip
encrypted material." Its canonical authority is the profile-portability ADR
(`2026-05-27-profile-portability-adr`), **not** the user-profile-backend-schema
ADR. D2 verbatim: "No encrypted blobs are included in the bundle. The bundle
contains decrypted pydantic domain-model payloads only. On import, each domain
object is re-encrypted under the recipient's own bucket DEK via the standard
`SecureObjectRepository.save()` path. This is the correct custody-transfer
pattern: data portability without key portability." Its rationale: strip the
*ciphertext / wrapped-DEK envelopes* — which are useless to a recipient who
lacks the originator passphrase and only widen the attack surface — and carry
the *decrypted payloads*, re-encrypting on import.

D2 therefore says nothing about dropping evidence; it is a key-custody rule.
The actual gap is in **D1**, which enumerated the bundle scope as facts + the
four financial-history categories and explicitly excluded only event-log
history — it never named evidence/attachments or the live/audit stores at all.
Meanwhile the secure-storage-production-hardening ADR
(`2026-05-22-secure-storage-production-hardening-architecture-adr`) names
`evidence` and `inventory` as first-class governed bucket repositories and
mandates fail-closed completeness for filing-grade output ("A readable subset is
not a complete ledger, filing history, wallet state..."). The new ADR extends
D1's enumerated scope; evidence rides as typed decrypted payload re-encrypted on
import, **exactly as the four categories already do**, fully consistent with D2.

## Test coverage gap

No test round-trips attachments or any live/audit store through export/import.
`test_bundle_reexports.py` only checks symbol re-exports (and does not even pin
the `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` value). `test_profile_export_roundtrip.py`
seeds the four structured categories and asserts strict pydantic equality plus a
`legal_refs` anti-tautology proof — a strong template — but seeds **no**
attachment bytes and **no** live state. `test_service_import_export.py` registers
only a profile; it asserts the label is absent from the cleartext archive and
that `BUCKET_EXPORTED` / `BUCKET_IMPORTED` events fire, but never seeds or
asserts any dropped store. The version constants are effectively unpinned by
value, so a schema bump breaks no existing assertion.

## Open decisions for the ADR

1. **Cleartext bundle vs. bytes.** Carrying evidence bytes into the cleartext
   JSON bundle escalates its sensitivity (raw invoice PDFs base64 on operator
   disk) and is in tension with `sensitive-financial-data-secure-storage-only`.
   The candidate is to split the two transports' contracts: only the sealed
   (AEAD-encrypted) archive carries bytes / live-state for full custody, while
   the cleartext portable bundle stays structured-only and emits a loud
   "evidence not included" Notice.

2. **Audit-trail provenance on import.** Bucket event ids are content-addressed
   (SHA-256 over seven fields via `derive_bucket_event_id` /
   `src/aeat/domain/buckets/_event.py:213-233`, enforced by `_enforce_derived_id`
   at `:269-282`), nothing references them as foreign keys, and the catalogue
   merge is idempotent by id. Preserving original ids/timestamps verbatim vs.
   re-stamping is a real choice with a content-addressing constraint.

3. **Manifest-digest honesty.** `manifest_digest` is a SHA-256 over the
   plaintext `BucketManifest` (`src/aeat/application/bucket_maintenance/_manifest_digest.py:30`;
   `BucketManifest` at `src/aeat/adapters/persistence/storage/bucket/_manifest.py:91-119`
   carries bucket-identity + KDF metadata only — no namespace or row-count
   enumeration). It is bound into AEAD associated data as a header tamper-anchor
   but has **zero** relationship to what the payload actually contains. Whether
   the sealed archive should assert and verify that its payload covers the bucket
   it claims to back up is open.

4. **Bundle schema version.** This is a backward-incompatible payload change in
   a pre-beta, no-legacy codebase (`no-legacy-compatibility`): the candidate is
   to bump `bundle_schema_version` (currently 2,
   `_portable_export.py:49`) and `_ARCHIVE_SCHEMA_VERSION` (currently 1,
   `_service.py:76`), delete the old shapes, and not bridge.

## Honoured rules

`aeat-roundtrip-discipline`, `ledger-evidence-bytes-not-links`,
`ledger-derived-revisions-bundle-evidence`,
`sensitive-financial-data-secure-storage-only`, `no-legacy-compatibility`,
`aeat-registry-authority-flow`, `service-imports-via-top-level-reexports`,
`aeat-architecture-boundaries`, `composition-service-no-parallel-write-path`.
