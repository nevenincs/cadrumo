---
tags:
  - '#adr'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
related:
  - "[[2026-06-14-storage-backend-security-review-research]]"
---



# `storage-backend-security-review` adr: `close the residual secure-storage security, enrollment, and standardisation gap` | (**status:** `accepted`)

## Problem Statement

A five-axis adversarial-and-structural audit of the secure-storage backend
(recorded in the same-feature research) surfaced eleven HIGH findings, ten
MEDIUM, and seven LOW against an otherwise sound at-rest pipeline. The findings
cluster into five concerns the prior production-hardening campaign did not close:
(1) two exploitable security edges that take sensitive bytes outside the hardened
path (export-archive HKDF sealing, decrypted PDF to `/tmp`); (2) an at-rest
integrity gap where the secure-object AEAD binds only the column type, not the
row identity, and the per-row integrity columns are written but never verified on
read — making intra-bucket row-substitution and stale-revision replay
undetectable; (3) concurrency and durability defects (no `busy_timeout`/WAL,
manifest write without fsync); (4) cross-machine persistence defects (absolute
`source_path` baked into persisted+exported records, non-deterministic bundle
payloads); and (5) standardisation/enrollment drift (namespace literals
duplicated outside the adoption gate's reach, a domain-layer hexagonal inversion,
private-submodule imports, route helpers bypassing the canonical wrapper). This
ADR is the authority node for the remediation campaign.

## Considerations

The governing architecture is the accepted
`2026-05-22-secure-storage-production-hardening-architecture-adr`: `StorageRuntime`
and the runtime-wrapper surface are the mandatory production storage boundary, the
namespace registry is the single source of truth, listing is fail-closed, and
secure objects carry revision lineage. The audit confirms that boundary is broadly
adopted; the remaining work is closing the enumerated gaps against it, not
re-architecting. Three project rules bear directly: `sensitive-financial-data-
secure-storage-only` (H1, H2), `aeat-schema-central-config` (H9), and
`no-legacy-compatibility` (H8, L3, L4). The pre-beta, no-released-data status is
load-bearing: it permits changing persisted shapes (the AEAD AAD scheme, the
`source_path` representation) outright rather than migrating, and it forces the
deletion (not maintenance) of the v1 bundle compat branch.

## Constraints

Work lands on the shared `chore/eliminate-shims` factory branch alongside
concurrent peer campaigns holding uncommitted WIP. Every change is one atomic
explicit-pathspec commit authored only over files with no peer WIP
(`git diff -- <file>` before edit; abort on non-authored changes), with the
destructive-git prohibition in force. No mocks/stubs/skips: each persistence-shape
change carries a strict non-default roundtrip test plus an anti-tautology proof.
The H3 AEAD change is the highest-risk item — changing the AAD invalidates every
existing encrypted row, which is acceptable only because no released data exists;
it must ship with its roundtrip and a read-time verification test that fails
closed on a corrupted hash. H7's architectural option (one row per transaction)
is larger than the rest and is sequenced last so the campaign is not blocked on
it; the tactical double-decrypt fix lands regardless.

## Implementation

Remediation proceeds in six blast-radius-ordered waves mirroring the architecture
ADR's discipline. Wave 1 closes the self-contained security edges: replace the
export-archive HKDF derivation with Argon2id and persist its params; eliminate the
`/tmp` PDF scratch by parsing in memory through the existing bytes path; add the
read-time Argon2 cost floor on the file-fallback KDF; delete the write-only `salt`
artefact and dead non-atomic writer. Wave 2 closes the at-rest integrity gap: bind
`namespace || object_key_digest || schema_version` into the secure-object payload
AEAD AAD and verify `payload_hash`/`revision_id` on every read, failing closed.
Wave 3 hardens concurrency/durability: WAL + `busy_timeout` + `synchronous=NORMAL`
on the bucket engine, fsync on the manifest atomic write, and re-validated lockfile
reclaim. Wave 4 fixes cross-machine correctness: relative/sha-only provenance, the
rename integrity-check label comparison, basename-only audit paths, deterministic
bundle payloads, and the manifest-digest contract (implement over a
timestamp-independent projection or correct the docstring). Wave 5 standardises and
completes enrollment: route every namespace literal through the registry constant
and extend the adoption gate to `domain/` and `adapters/outbound/`; resolve the
fincas hexagonal inversion; rebind private-submodule imports; consume the canonical
wrapper from the three route helpers; delete the v1 bundle branch; confirm/extend
the SQL-store rotation contract. Wave 6 addresses performance: kill the
`attach_evidence` double-decrypt and thread one catalogue per command, then the
per-transaction-row redesign and streaming enumeration.

## Rationale

The selected approach closes gaps against the existing architecture rather than
introducing a new one, because the audit's baseline section confirms the at-rest
crypto, envelope schema discipline, and runtime-wrapper enrollment are sound. The
H3 ordering (immediately after the self-contained edges) reflects that it is the
highest-confidence finding — independently corroborated by two axes — and the most
structurally central: every secure-object read inherits its guarantee. Sequencing
the standardisation and enrollment work after the security and correctness fixes
keeps operator-facing safety ahead of hygiene, matching the architecture ADR's
"custody and runtime gates land first" backlog ordering.

## Consequences

The campaign hardens the export surface against offline attack, makes at-rest
tampering detectable, removes the last decrypted-bytes-to-disk path, and makes the
backend correct across machines and concurrent invocations. The cost is real: the
H3 AAD change and the `source_path` change invalidate any existing local bucket
data, acceptable only under the pre-beta no-legacy posture; an operator with a
pre-campaign bucket re-provisions. WAL introduces a sidecar `-wal`/`-shm` file per
bucket DB that the bucket layout and export/seal paths must tolerate. The
adoption-gate extension will fail CI until every duplicated namespace literal is
routed through the registry, which is the intended ratchet. Several findings
(H3 AAD, M1 digest, M9 rotation) are candidates for promotion into project rules
once their fixes land and prove durable.

## Codification candidates

- **Rule slug:** `secure-object-aead-binds-row-identity`.
  **Rule:** Every secure-object payload AEAD must bind the row identity
  (`namespace`, `object_key` digest, `schema_version`) as associated data, and
  every read must verify the stored payload hash and revision id before returning,
  failing closed on mismatch.
- **Rule slug:** `persisted-records-carry-no-absolute-host-paths`.
  **Rule:** No persisted or exported record, manifest, or audit-event payload may
  store a resolved absolute filesystem path; provenance is a relative name or a
  content hash, so records stay portable and roundtrip-equal across machines.
- **Rule slug:** `namespace-strings-resolve-through-the-registry`.
  **Rule:** Every secure-object namespace string in production code must reference
  its `STORAGE_NAMESPACE_REGISTRY` definition, enforced by an adoption gate that
  scans `application/`, `domain/`, and `adapters/outbound/`.
