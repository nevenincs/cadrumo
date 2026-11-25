---
tags:
  - '#adr'
  - '#modelo-runtime-performance'
date: '2026-11-09'
modified: '2026-11-09'
body_schema: 'body-v2'
body_hash: 'sha256:3598cc20a6ce45b1e917bd43c113fb0468ded22ff3ce2d9486f1892eacd7231b'
related:
  - "[[2026-10-07-modelo-runtime-performance-audit]]"
  - "[[2026-10-07-modelo-runtime-performance-plan]]"
  - "[[2026-10-05-google-outbound-review-adr]]"
  - "[[2026-07-09-compatibility-lifecycle-adr]]"
  - "[[2026-08-22-secure-storage-performance-hardening-adr]]"
  - "[[2026-11-05-cold-start-performance-secure-storage-core-adr]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]"
  - "[[2026-06-10-ledger-modelo-crossref-adr]]"
  - '[[2026-06-14-storage-backend-security-review-adr]]'
---

# `modelo-runtime-performance` adr: `Deduplicate saved registry rendering snapshots by content digest` | (**status:** `accepted`)

Accepted 2026-11-09. Basis: the operator ordered on 2026-11-09 that the Modelo 303 edit latency, 2.4 to 2.9 s and growing with every saved revision, be handled, and the coordinator routed that instruction to this decision.

## Problem Statement

The calculation-revision catalogue is one encrypted secure-object row per profile (`src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:1200`). Every saved revision embeds its complete public registry rendering snapshot (`src/cadrumo/domain/modelos/calculation_revision.py:499`, `src/cadrumo/domain/modelos/calculation_revision_rendering.py:336`). For modelo 303 one snapshot serializes to about 2.6 MB. Every revision of the same declaration normally embeds the same snapshot.

Each read decodes the whole row (`src/cadrumo/adapters/persistence/profile/modelos_calculation.py:258`). Each write re-encodes, encrypts and stores it whole (`src/cadrumo/adapters/persistence/profile/modelos_calculation.py:442`, `src/cadrumo/adapters/persistence/profile/modelos_calculation.py:498`). A `modelo.edit.apply` therefore costs about 0.25 to 0.33 s per stored revision. APP-QA measured successive edits at 0.6, 1.2, 1.5, 3.1 and 5.8 s, and a 5.878 s hold of the runtime profile-admission guard. Session admission, connection sessions and extension records queue behind that hold. The cost grows with every revision the profile has ever saved.

A behaviour-preserving mitigation is prepared separately. It reuses a decoded catalogue within one repository instance and serializes each live snapshot object once. It does not change the persisted format. Composition builds a repository per operation, so each operation still decodes and rewrites every embedded snapshot. Removing the linear term requires a persisted-format decision, which the `2026-10-07-modelo-runtime-performance-plan` routes to decision coverage.

## Considerations

- Revision identity hashes only the rendering triple `authority_generation`, `registry_digest` and `rendering_digest`, never the snapshot body (`src/cadrumo/domain/modelos/calculation_revision_identity.py:559`). Moving the body does not change any `calculation_revision_id`.
- `rendering_digest` already content-addresses the shareable body: the complete registry payload, the saved labels and the directory identities (`src/cadrumo/domain/modelos/calculation_revision_rendering.py:425`, `src/cadrumo/domain/modelos/calculation_revision_rendering.py:438`). The model validator recomputes both digests on every decode (`src/cadrumo/domain/modelos/calculation_revision_rendering.py:382`).
- A saved rendering is a self-contained immutable capture under the calculation pin (`src/cadrumo/domain/modelos/calculation_revision_rendering.py:397`, `src/cadrumo/application/modelo/revision_persistence.py:470`). Renderers consume the saved snapshot and never a current template (`2026-10-05-google-outbound-review-adr` constraint 8; `src/cadrumo/application/export/review_form_data.py:121`). Published authority generations are retired by cleanup (`2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr`), so a snapshot cannot be re-resolved from authority later.
- `apply_batch` commits writes, digest-addressed deletions and revision assertions in one SQL transaction (`src/cadrumo/adapters/persistence/storage/sql/secure_object_writes.py:188`). A write whose `expected_revision_id` is `ABSENT_SECURE_OBJECT_REVISION_ID` creates only when absent (`src/cadrumo/core/secure_object_write.py:40`). The participation index is the precedent for a derived namespace co-committed with the catalogue (`src/cadrumo/adapters/persistence/profile/participation_index.py:225`, `2026-06-10-ledger-modelo-crossref-adr`).
- Payload AAD binds namespace, HMAC key digest and schema version (`src/cadrumo/adapters/persistence/storage/crypto/encrypted_columns.py:51`, `src/cadrumo/adapters/persistence/storage/sql/secure_object_row_codec.py:242`). The row codec refuses any version below current because no upgrader is registered (`src/cadrumo/adapters/persistence/storage/schema_lineage.py:38`). Bumping the catalogue namespace version would make every existing catalogue unreadable.
- Every read verifies the stored payload hash and revision id, and the AAD binding makes substituting a row under another key detectable (`2026-06-14-storage-backend-security-review-adr`, wave 2). Its pre-beta permission to change persisted shapes without migration no longer applies to taxpayer catalogues that profiles already hold.
- Released taxpayer data must stay readable, and a real schema transition needs its owning reader and a production-path restorability proof (`2026-07-09-compatibility-lifecycle-adr`, amendment 2026-09-08).
- Pure reads must not repair or re-persist (`2026-08-22-secure-storage-performance-hardening-adr`). The SQL write funnel, revision-guarded batches and the `BEGIN IMMEDIATE` writer reservation stay as decided in `2026-11-05-cold-start-performance-secure-storage-core-adr`.
- The measurements above come from the APP-QA session and the prepared mitigation. No vault Reference or Audit records them yet.

## Considered options

- **Status quo plus the mitigation.** No format risk, and it removes repeated decodes inside one operation. Rejected as the end state: each operation still decodes, encrypts and writes N snapshots, so edit latency and guard hold stay linear in stored revisions. It is kept as phase 0.
- **Compress the catalogue payload in place.** Shrinks bytes at rest. Rejected: JSON decode, validation and encode stay per revision, and those dominate the measured cost. A 2.6 MB repeat also exceeds common compression windows. It also adds a codec inside the AEAD-bound payload.
- **One secure-object row per revision, each with its embedded snapshot.** Makes an edit write one row. Rejected: storage stays N times the snapshot size, and every validated load still decodes all N snapshots. The singleton revision guard that the co-commits rely on would need a new concurrency token.
- **Store only the rendering triple and re-resolve the snapshot from the published authority.** Smallest rows. Rejected: retired generations are cleaned up, and the immutable-rendering commitment forbids substituting current authority.
- **Store each distinct rendering snapshot once in a sibling profile namespace, addressed by its rendering digest, with revisions holding a typed reference.** Chosen. Storage, decode and write cost scale with distinct snapshots rather than revisions. Revision identity and the existing integrity checks are unchanged.

## Constraints

1. Persisted identities stay fixed. The catalogue keeps namespace `cadrumo.domain.modelos.calculation_revisions`, its singleton key, `FINANCIAL` sensitivity, schema version 4 and its AAD. No reset, no new-key-store migration, no DEK export and no re-encryption of existing rows outside an ordinary write.
2. Legacy embedded revisions keep decoding through the existing path for as long as a profile, sealed archive, mirror or import can hold one. Removing that reader requires a separate decision with a supported window.
3. The reference form is a distinct typed shape with an explicit discriminator. The reader never infers it from missing fields. It is declared in the `record_formats` of the catalogue namespace. An unknown discriminator refuses the catalogue.
4. Snapshot rows live only in the owning profile bucket. They are encrypted under the profile DEK, classified `FINANCIAL`, scoped `PROFILE_LOCAL` and enrolled in `DOMAIN_NAMESPACE_DEFINITIONS` (`src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:1226`). The content is public, but its presence shows which modelo, year and period a taxpayer calculated. No plaintext row, no `CORPUS` plaintext allowance, no store shared across profiles and no use of the published authority as storage. Every taxpayer value, input, provenance and lifecycle fact stays on the private revision.
5. A snapshot row holds only the shareable body: registry payload, saved labels and directory identities. `authority_generation`, `registry_digest` and `rendering_digest` stay on the reference of each revision. The row carries no authority, grade or generation claim, and no operation resolves calculation authority from it.
6. Snapshot rows are immutable. A writer creates a row only when absent and never rewrites one.
7. A catalogue write commits only if every digest it references is present at commit time: written in the same `apply_batch` transaction or asserted present inside it. This holds for every caller that composes the catalogue write into the batch of another repository. Atomicity is claimed only for that single SQL transaction. SQLite WAL with `synchronous=NORMAL` can still lose the whole last transaction on power failure, but never half of it.
8. Reads verify before use. AEAD binds a row to its key. The envelope classification and version are checked. The hydrated `CalculationRenderingSnapshot` must recompute the `registry_digest` and `rendering_digest` the revision claims, and the revision must re-derive its own identity. A missing, unreadable or mismatched row refuses the catalogue load with a typed `CalculationRevisionPersistenceError` reason. A reader never drops the rendering, never substitutes current authority and never guesses. Dropping it would also change the derived revision identity and fail validation.
9. Ordinary writes never delete snapshot rows. Rows leave the store only with profile deletion or reset, or through an explicit reclaim operation. That operation deletes only digests that no stored revision references, asserts the catalogue revision it read, and refuses on any unreadable revision.
10. Revision identity is unchanged. `calculation_revision_id`, `registry_digest`, `rendering_digest`, `authority_generation`, filing grade and every receipt or report derived from a hydrated revision keep their values and meaning. Only the bytes, `payload_hash` and secure-object revision of the catalogue row change, as they already do on every write.
11. One operation uses one authority generation, as before. Revisions of different generations may share one row only when their rendering digests are equal, which means byte-identical bodies. Hydration attaches the generation claim of each revision.

## Implementation

We will store each distinct saved rendering body once, in a new profile-local secure-object namespace keyed by its `rendering_digest`. Each `CalculationRevision` will persist a typed reference instead of the embedded body. The domain model is unchanged: `CalculationRevision.rendering_snapshot` still holds a complete `CalculationRenderingSnapshot` after load. The persistence adapter alone externalizes on write and hydrates on read.

Namespace. A new `SecureObjectNamespaceDefinition` beside the catalogue, owner `cadrumo.domain.modelos`, one row per 64-hex rendering digest, structured custody, with the same mirror policy as the catalogue. The namespace string, registry key and first schema version are implementation choices within constraint 4.

Write. `CalculationRevisionCatalogueRepository` emits a write unit, not one write. The unit holds the catalogue row in reference form, create-if-absent writes for referenced digests not yet stored, and presence assertions for referenced digests already stored. Presence is read from decryption-free key digests (`src/cadrumo/adapters/persistence/storage/sql/secure_object_writes.py:166`). The methods `save`, `to_secure_object_write` and `save_with_secure_object_writes` (`src/cadrumo/adapters/persistence/profile/modelos_calculation.py:397`, `src/cadrumo/adapters/persistence/profile/modelos_calculation.py:442`, `src/cadrumo/adapters/persistence/profile/modelos_calculation.py:471`) and the domain protocol (`src/cadrumo/domain/modelos/protocols.py:32`) change together. All composing callers change atomically: `src/cadrumo/application/modelo/revision_persistence.py:306`, `src/cadrumo/application/modelo/revision_persistence.py:435`, `src/cadrumo/application/modelo/filing_revision_persistence.py:911`, `src/cadrumo/application/modelo/filing_chain_reconciliation.py:922`, `src/cadrumo/application/modelo/amendment_actions.py:1076` and `src/cadrumo/application/modelo/verification_actions.py:570`. Batches owned by other repositories accept the assertions of the unit. Two writers creating the same new digest concurrently produce an ordinary revision conflict on the second; the existing conflict handling applies and no revision is lost.

Read. The repository loads the catalogue row and collects the distinct referenced digests. It loads and verifies each snapshot row once, then validates the catalogue with those bodies supplied through validation context. The rendering validator (`src/cadrumo/domain/modelos/calculation_revision_rendering.py:356`) and the verified-registry memo (`src/cadrumo/domain/modelos/calculation_revision_rendering.py:298`) keep their roles. Legacy embedded entries take the existing decode.

Conversion. No migration operation and no read repair. The first ordinary write after upgrade writes every revision, legacy ones included, in reference form, with all distinct snapshot rows in the same transaction. Until a profile writes again, its legacy catalogue stays byte-identical and readable.

Export and custody. The portable bundle exports hydrated revisions (`src/cadrumo/application/user_profile/bundle.py:92`), so the bundle format and `BUNDLE_SCHEMA_VERSION` are unchanged and the bundle still carries one embedded snapshot per revision. Import re-saves through the repository and yields reference form. The new namespace joins `_TYPED_CATEGORY_NAMESPACES` (`src/cadrumo/adapters/persistence/storage/profile_custody_carry.py:94`), so it is neither carried twice nor left unclassified; an unclassified namespace would refuse a full export (`src/cadrumo/application/user_profile/custody_carry.py:59`). The accountant review package carries the revision id, coordinate and ledger evidence, not the rendering (`src/cadrumo/application/modelo/review_package.py:292`), so it is unaffected. Calculation reports, saved-form review and workbooks consume the hydrated revision and produce identical output. Encrypted mirror push and restore must treat the catalogue and snapshot namespaces as one unit. A catalogue restored without its snapshots refuses under constraint 8.

Rollout, as hypotheses within the constraints:

- Phase 0: land the prepared mitigation unchanged.
- Phase 1: add the namespace, the snapshot row codec and the two-form reader, with a frozen legacy fixture written by the current writer on synthetic data.
- Phase 2: switch the writer and every composing caller in one change.
- Phase 3: add missing-row and orphan reporting to the integrity diagnostics. The explicit reclaim operation in constraint 9 is optional later work.

Verification, all through the real repository, encrypted store and owning validators:

- Round trip. A legacy catalogue loads equal. After one write it is in reference form and reloads equal. `calculation_revision_id`, both digests, the generation and `capture_review_form` output are equal before and after.
- Per supported year. Enumerate the years from the registry envelope through the catalogue in `src/cadrumo/domain/calculations/registry/snapshot_globals.py`, never from a list. For each modelo whose calculation captures a rendering (`src/cadrumo/application/modelo/calculation_actions.py:451`), prove round-trip parity at every authored and projected edition, and that no existing capability regresses.
- Refusals. A missing row, a tampered row, a row moved under another key, a row with a valid AEAD but the wrong digest, an unknown reference discriminator, and a write whose referenced row was removed before commit. Each refuses.
- Concurrency and crash. Concurrent writers of the same digest lose no revision and leave no orphan. A process killed mid-batch leaves either both the catalogue and its snapshot rows or neither.
- Custody. A full portable export succeeds and its import round-trips. Profile deletion and reset remove the snapshot rows. A mirror push of only one of the two namespaces is detected on restore.
- Performance. Use real subprocesses and persisted profiles, per `2026-08-22-secure-storage-performance-hardening-adr`. Show that edit-apply latency, admission-guard hold and catalogue bytes stay flat as stored revisions grow, apart from at most one new snapshot per write. Report medians; no single-host threshold is a gate.
- Repository gates: `just check-import-boundaries`, `just check-types`, `just check-style`, `just test-registry`, and the operation contract manifest if any public schema moves.

## Rationale

Content addressing removes the linear term at its source: identical public bodies stored N times inside one private row. The digest it needs already exists and is already verified on every decode, so the change adds no new integrity primitive and leaves revision identity untouched. A sibling namespace in the same SQLite store keeps atomicity real: one `apply_batch` transaction, the mechanism the participation index already uses. Every rejected option fails a knockout. Status quo and compression leave per-revision decode in place. Per-revision rows keep N copies and lose the singleton guard. Re-resolution breaks the immutable saved-rendering commitment.

Keeping catalogue version 4 and adding a discriminated record format preserves AEAD identities and legacy readability without upgrader machinery that does not exist today. Write-time conversion respects the pure-read rule.

## Consequences

- Edit-apply cost, admission-guard hold and catalogue size become proportional to distinct snapshots, typically one per declaration and edition, rather than to saved revisions. Snapshot bytes at rest drop by roughly N to 1 per declaration.
- The repository write contract widens from one write to a write unit. Six application call sites and any repository batch that embeds the catalogue change in one coordinated step.
- A missing or corrupt snapshot row refuses the whole catalogue, as a corrupt revision does today. A single bad row now affects every revision that shares it. Per-revision quarantine is not decided here.
- An older build reading a converted catalogue refuses it as an invalid payload rather than as written by a newer application. It does not misread it.
- Portable bundles stay as large as today. Deduplicating inside the bundle is a separate bundle-schema decision.
- Out of scope: bundle-format deduplication, per-revision catalogue rows, lazy or partial hydration, compression, sharing across profiles, the per-load resolution of 303 registry snapshots for rectificativa validation (`src/cadrumo/adapters/persistence/profile/modelos_calculation.py:380`), automatic garbage collection, and authority-store retention.
- Reconsider if a released build must show a version-specific refusal on downgrade, if mirror tooling cannot treat the two namespaces as one unit, or if measurement shows distinct snapshots per profile growing at the same rate as revisions.

## Reconciliation with existing decisions

This is a new ADR, not an amendment. No accepted ADR decides the persisted layout of saved rendering snapshots or the singleton embedding. The decisions it touches stay in force without rewording:

- `2026-10-05-google-outbound-review-adr` constraint 8: renderers still consume one immutable snapshot under the generation and registry digest of the revision.
- `2026-07-09-compatibility-lifecycle-adr`: legacy rows keep a production reader, and the round-trip proof is the required restorability evidence.
- `2026-08-22-secure-storage-performance-hardening-adr` and `2026-11-05-cold-start-performance-secure-storage-core-adr`: no read repair, and the write funnel, guards and transactions are unchanged.
- `2026-06-10-ledger-modelo-crossref-adr`: the index keeps co-committing in the same batch.
- `2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr`: published authority is not used as profile storage.
- `2026-06-14-storage-backend-security-review-adr`: the new namespace resolves through the namespace registry, and its rows inherit the AAD row binding and read-time hash verification.

The completed `2026-10-07-modelo-runtime-performance-plan` excluded new persisted formats from its own scope and routed them to decision coverage. This record is that coverage. The wording of that plan stays historical.

The code docstring at `src/cadrumo/domain/modelos/calculation_revision_rendering.py:163`, which says every saved calculation revision embeds the complete snapshot, is updated with the implementation, not here.
