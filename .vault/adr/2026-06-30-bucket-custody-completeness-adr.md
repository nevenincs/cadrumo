---
tags:
  - '#adr'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
related:
  - "[[2026-06-30-bucket-custody-completeness-research]]"
  - '[[2026-05-27-profile-portability-adr]]'
  - '[[2026-06-03-bucket-sealed-archive-adr]]'
  - '[[2026-06-03-cli-workflow-redesign-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
---

# `bucket-custody-completeness` adr: `full per-bucket export/import custody` | (**status:** `accepted`)

## Problem Statement

Per-bucket export/import does not round-trip the full durable bucket. Both
custody transports — the cleartext `aeat config profile export`/`import` and the
sealed recovery-archive `BucketMaintenanceService.export`/`import_` — share one
payload builder, `serialize_profile_bundle`
(`src/cadrumo/application/user_profile/_bundle.py:47-88`), that carries exactly five
categories (profile, work units, ledger transactions, calculation revisions,
filing records). Every other durable per-bucket secure-object store is silently
dropped. A "restore" therefore returns a structurally-incomplete profile:

- **Evidence is broken.** Attachment/evidence bytes and manifests
  (`cadrumo.domain.attachments.blobs`/`.manifests`) are not carried, yet
  transactions and revisions reference evidence by id only
  (`Transaction.attachment_ids`, `LedgerEvidenceRow`). After restore those ids
  resolve to `AttachmentNotFoundError` — violating `ledger-evidence-bytes-not-links`
  and `ledger-derived-revisions-bundle-evidence`.
- **Cross-period calculation inputs are orphaned.** Filed-revision observations
  (`cadrumo.calculations.observations`), IVA compensation history, and IVA-wallet
  reconciliation decisions are the 303 carry-forward inputs. Dropping them
  silently corrupts every future-period calculation after the restore — a
  silent under-declaration class.
- **The audit trail and live captures vanish.** The bucket event-history
  catalogue, censo snapshots, and AEAT-signed justificante-capture receipts are
  all dropped.
- **The sealed archive lies about completeness.** Its header `manifest_digest`
  is computed over the plaintext `BucketManifest` (bucket-identity + KDF
  metadata only) and has zero relationship to the payload, so a partial bundle
  seals and presents as a full recovery archive.

No test covers any of this (the research document grounds each gap with
file:line evidence). The agent-harness feature names "data custody & recovery" a
first-class operator workflow and assumes this backbone is solid; this ADR makes
it so. It is a new-feature ADR derived from the research; it introduces no code,
only the decided shape and the resolution of four open questions.

## Considerations

**The canonical namespace registry is the design lever.** Every secure-object
namespace is declared once in `STORAGE_NAMESPACE_REGISTRY`
(`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:865`) with a
`scope` field (`PROFILE_LOCAL`/`BUCKET_LOCAL`/`PROCESS_LOCAL`). That field
authoritatively answers "is this store keyed by `{bucket_id}`?" and is the
natural enumeration source for both the carry set and a coverage gate. The
`browse` verb already projects the live populated namespaces with row counts via
`SecureObjectRepository.list_namespaces()` (`_service.py:273-281`); the transport
must consume the same authority rather than a hand-maintained category list, per
`aeat-registry-authority-flow`.

**D2 is a key-custody rule, not an evidence-exclusion rule.** The
"strip encrypted material" decision (`2026-05-27-profile-portability-adr`, D2)
means strip *ciphertext / wrapped-DEK envelopes* and carry *decrypted domain
payloads*, re-encrypting under the recipient bucket DEK on import — "data
portability without key portability." The bundle's incompleteness is in D1's
enumerated scope, which never named evidence or the live/audit stores. This ADR
**extends D1**; evidence rides as typed decrypted payload re-encrypted on import,
exactly as the four structured categories already do — fully consistent with D2.

**The composition discipline binds.** `BucketMaintenanceService` is a thin
composition layer over single-writer primitives
(`composition-service-no-parallel-write-path`); the new carry must delegate every
write to the owning repository's save path and emit, not re-implement. The new
bundle symbols must be consumed through package `__all__` re-exports
(`service-imports-via-top-level-reexports`).

**Sensitivity gradient across transports.** Attachment bytes are FINANCIAL
(raw invoice/bank-document bytes); justificante captures are FINANCIAL
(AEAT-signed receipts). `sensitive-financial-data-secure-storage-only` forbids
persisting those bytes to a plaintext side store on operator disk. The cleartext
JSON bundle is exactly such a side store; the sealed archive is AEAD-encrypted at
rest under a recovery KEK and is not. The two transports therefore cannot carry
the same set, which directly forces Decision 1.

**Bucket-local re-keying is a non-issue for recovery.** `import_` restores under
`header.bucket_id` — the same id the archive was exported from — so `BUCKET_LOCAL`
object keys (which embed the bucket id, not the DEK) are unchanged; re-saving the
typed snapshots reproduces the keys and the justificante bucket-match guard
passes. Re-encryption under the fresh DEK still happens. Re-homing to a different
bucket id is out of scope.

## Considered options

**Decision 1 — Cleartext bundle vs. carrying bytes.**
- *Both transports carry everything (bytes in cleartext JSON):* simplest, one
  shape — but base64 invoice PDFs and AEAT receipts land in plaintext on operator
  disk, violating `sensitive-financial-data-secure-storage-only`. Rejected.
- *Neither transport carries bytes (structured-only everywhere):* preserves the
  status quo's safety but leaves "data custody & recovery" structurally broken —
  no full backup exists. Rejected.
- **Chosen — split the transports' contracts.** The **sealed archive** carries
  the full durable set (evidence bytes + live/audit state); it is AEAD-encrypted
  at rest, so the bytes never sit in cleartext. The **cleartext bundle** stays
  structured-only (the four categories plus the structured cross-period calc
  inputs — observations / IVA history / wallet decisions, which are typed
  AUDIT-class records of the same kind it already carries, *not* raw document
  bytes), carries **no** attachment bytes and **no** byte-bearing live snapshots,
  and emits a loud `Notice` that it is not a full backup and names the sealed
  archive as the complete-custody transport.

**Decision 2 — Audit-trail provenance on import.**
- *Re-stamp event ids/timestamps at import:* would make the audit say each
  historical event "occurred" at import time and, because ids are content-
  addressed, would require minting new ids — destroying the content-addressing
  invariant and the meaning of the trail. Rejected.
- **Chosen — preserve original event ids and timestamps verbatim.**
  `derive_bucket_event_id` content-addresses the id over seven fields
  (`src/cadrumo/domain/buckets/_event.py:213-233`) and `_enforce_derived_id`
  (`:269-282`) rejects any id that does not match its content, so an event can
  only be carried *with* its original fields; the catalogue merge is idempotent
  by id and nothing references ids as foreign keys. The import's own
  `BUCKET_IMPORTED` event is appended separately with a freshly-derived id and
  the import timestamp, correctly layering "operator restored this bucket at T"
  on top of the carried history.

**Decision 3 — Manifest-digest honesty.**
- *Leave the manifest digest as the only integrity anchor:* keeps a partial
  bundle presenting as a full archive — the defect itself. Rejected.
- *Replace the manifest digest with a payload digest:* loses the existing AEAD
  header tamper-anchor for no gain. Rejected.
- **Chosen — add a payload coverage manifest and assert it at build, keeping the
  manifest digest as the header anchor.** At export, enumerate the source
  bucket's populated namespaces (the `list_namespaces()` authority the `browse`
  verb uses), and for the sealed (full-custody) transport **fail closed** if any
  populated, in-scope, non-excluded namespace is not represented in the payload —
  so "full backup" is true by construction and a future new store added without
  wiring it into the carry is caught loudly (`no-silent-under-declaration`). The
  bundle records a typed coverage manifest (namespaces carried + row counts) that
  the importer and an audit can verify. The cleartext transport declares a
  structured-only coverage profile whose deliberate exclusions are surfaced as
  the Decision-1 Notice, never silently.

**Decision 4 — Bundle / archive schema version.**
- *Add optional fields without a version bump* (permitted by the old portability
  D4 for additive optional fields): rejected — this is a custody-completeness
  change where a v2 reader silently producing an incomplete restore is the
  failure mode; the version must move so an old payload is refused, not partially
  honoured.
- **Chosen — bump both and delete the old shapes.** `bundle_schema_version`
  2→3 (`_portable_export.py:49`) and `_ARCHIVE_SCHEMA_VERSION` 1→2
  (`_service.py:76`); `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` becomes `frozenset({3})`
  (the code already narrowed to `{2}` per `no-legacy-compatibility`); no bridge,
  no read-tolerance of the old shape — old is deleted, refused at the boundary.

## Constraints

This ADR layers on three accepted parents and treats them as stable. The
**profile-portability ADR** (`2026-05-27-profile-portability-adr`) owns the
bundle contract (D1 scope, D2 key-custody, D3 provenance, D5 idempotency); this
ADR extends D1 and re-affirms D2/D3/D5, it does not contradict them. The
**bucket sealed-archive ADR** (`2026-06-03-bucket-sealed-archive-adr`) owns the
container (no-plaintext-secrets, recovery-wrap, `archive_schema_version`); the
new coverage manifest rides inside the existing encrypted payload, not as a new
plaintext member. The **secure-storage-production-hardening ADR**
(`2026-05-22-secure-storage-production-hardening-architecture-adr`) names
`evidence` a governed bucket repository and mandates fail-closed completeness —
the authority this ADR's coverage gate enforces at the transport boundary.

No frontier dependencies: every carried store already has a typed payload and a
single-writer save path, and the namespace registry already declares scope. The
one genuine risk is **key-management correctness** — the import must re-encrypt
each carried object under the freshly-provisioned recipient DEK through the
owning repository's save path; a carried object written under any other key
schedule would be unreadable. This is bounded by reusing the existing save paths
(no new crypto primitive) and is the design's load-bearing test obligation.

The shared dirty worktree forbids destructive git/workspace operations; all work
is additive and path-scoped.

## Implementation

A registry-driven completeness layer over the existing composition transports;
no new write path. Authored across four cohesive areas.

**Carry-set derivation from the registry.** A single function partitions
`STORAGE_NAMESPACE_REGISTRY` into: structured-portable stores, byte/live stores
(carried only by the sealed transport), and the explicit exclude set (the
rebuildable participation index, `PROCESS_LOCAL`). The carry set is derived from
the `scope` field and an explicit per-namespace custody-policy tag, never a hand-
maintained list, so a newly-registered store is forced to declare its transport
disposition.

**Extended payload model.** `UserProfilePortableExport` v3 gains typed,
default-empty fields for the new stores: the structured cross-period inputs
(observations, IVA compensation history, wallet decisions + their immutable event
rows), the bucket event-history catalogue, the live snapshots (censo,
justificante-capture, notifications, expedientes), justificante metadata, and the
attachment set carried as typed `(manifest, bytes)` pairs. It also carries a typed
coverage manifest. Every field is a decrypted domain payload (D2); no envelopes
or key material.

**Transport-aware serialise/deserialise.** `serialize_profile_bundle` gains a
custody-profile parameter (structured-only vs. full). The full profile reads
attachment bytes via `AttachmentStore.iter_manifests` + `read_bytes` and each
dropped store via its owning repository; it computes the coverage manifest and
asserts full coverage (fail-closed). The structured profile omits the byte/live
stores and records their exclusion in the coverage manifest for the Notice.
`deserialize_profile_bundle` re-saves each carried store through its owning
repository save path (re-encrypting under the recipient DEK): attachments via
`put_bytes`/`write_manifest` (ids reproduce from the byte digest), observations /
IVA / wallet via their repositories, the event catalogue merged idempotently by
content-addressed id, the live snapshots under the restored same-id bucket
session. After import it triggers `rebuild_participation_index` rather than
carrying the derived cache.

**Coverage gate + honesty.** The sealed `export` enumerates the source bucket's
populated namespaces and refuses to write an archive that does not cover them;
`import_` verifies the coverage manifest against the payload. The existing
`manifest_digest` AEAD anchor is retained unchanged.

**Tests (per `aeat-roundtrip-discipline`).** Extend the existing strict-equality
roundtrip to seed *every* carried store with non-default state, push through the
real sealed-archive + crypto cycle, and assert strict pydantic equality on each
store (attachments by re-read bytes and reproduced id; observations/IVA/wallet by
value; event history by catalogue equality including ids). Add an anti-tautology
proof per new boundary (corrupt the on-disk/in-archive payload, assert refusal or
strict inequality) and a coverage-gate negative (a populated-but-uncarried
namespace fails the sealed export). Assert the cleartext transport emits the
"not a full backup" Notice and carries no attachment bytes.

## Rationale

The split-contract decision (1) is forced by the sensitivity gradient: the sealed
archive is the only transport that can hold FINANCIAL bytes without breaching
`sensitive-financial-data-secure-storage-only`, and "data custody & recovery"
needs exactly one true full-backup transport — the sealed archive — while the
cleartext bundle stays a structured, shareable, non-secret artifact that is
honest about what it omits. Preserving event provenance (2) is not a preference
but a consequence of content-addressing: the id *is* the content, so verbatim
carry is the only shape that keeps the audit trail meaningful and the validator
satisfied. The coverage gate (3) converts "is this backup complete?" from an
un-checkable property into a build-time invariant grounded in the same namespace
authority the runtime already trusts, mirroring the fail-closed completeness the
secure-storage ADR demands and the advisory-vs-blocking posture of
`no-silent-under-declaration`. The version bump with deletion (4) is the
`no-legacy-compatibility` default for a pre-beta payload change whose silent-
partial-restore failure mode makes refusing the old shape the safe choice. Every
decision extends an accepted parent rather than contradicting it, and the
research grounds each in file:line evidence.

## Consequences

A restored bucket is whole: evidence resolves, the audit trail and live captures
survive, and — most importantly — the cross-period 303 carry-forward inputs are
present, so a post-restore calculation is correct rather than silently
under-declared. The sealed recovery archive becomes a true full backup whose
completeness is structurally enforced, giving the agent-harness "data custody &
recovery" workflow the solid backbone it assumes. The cleartext bundle stays a
safe, shareable structured artifact that no longer pretends to be a backup.

Honest difficulties. The payload grows substantially (attachment bytes inflate
the sealed archive); this is inherent to a real backup, but large-attachment
buckets produce large archives. The full serialise/deserialise now touches many
repositories, widening the surface that must stay correct under the
re-encryption-on-import contract — the roundtrip and anti-tautology tests are the
load-bearing guard and must seed genuinely non-default state in every store or
the coverage is illusory. The coverage gate must enumerate from the registry, not
a literal list, or it silently rots the moment a new store is added; the gate's
own negative test defends this. Bucket-local re-homing (import under a *different*
bucket id) remains unsupported and must refuse loudly rather than silently write
mismatched keys.

Pathways opened. The registry-derived carry set and coverage manifest become the
single authority for "what is a complete bucket," reusable by a future integrity-
audit verb, by the agent-harness custody skill, and by any later cross-host
migration that does opt into re-keying. Once the coverage gate exists, adding a
new durable store is self-policing: it must declare its transport disposition or
fail the gate.
