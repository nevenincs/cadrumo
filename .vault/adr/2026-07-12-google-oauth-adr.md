---
tags:
  - "#adr"
  - "#google-oauth"
date: '2026-07-12'
related:
  - "[[2026-07-12-google-oauth-research]]"
supersedes:
modified: '2026-07-17'
---

# `google-oauth` adr: `remote ciphertext manifest mirror boundary` | (**status:** `accepted`)

## Problem Statement

The accepted 2026-05-13 Drive-sync ADR requires a local
`secure_objects_sync_state` table, a `DriveSync` coordinator, payload-decrypting
namespace label derivation, and a general `push`/`pull`/`status`/`orphans`/`claim`
command matrix. None of that operating model exists. The working mirror instead
derives its expected state from secure-object ciphertext rows at push time and
persists one remote integrity manifest per namespace. Leaving both descriptions
accepted makes a nonexistent local sidecar appear required and misstates the
operator surface.

This ADR supersedes `2026-05-13-google-oauth-adr` in whole. It redefines the
complete Drive substrate-mirror boundary, including the parts of the former ADR
that survive in a different implementation. `2026-05-12-google-oauth-adr`
remains accepted for the provider protocol and its placement beside the secure
repository. `2026-05-13-google-oauth-snapshot-adr` remains a separate, unbuilt
escrow/restore scope; it does not authorize a general pull or restore command.

## Considerations

- `SecureObjectRepository.iter_all_records_raw()` supplies deterministic,
  revision-bearing, on-wire ciphertext without decrypting it. The local
  repository remains the only authority.
- The shipped mirror writes ciphertext objects and a versioned manifest in the
  remote `_sync-state` namespace. The manifest is integrity metadata, not an
  encrypted payload and must not contain plaintext domain data or key material.
- Current CLI help exposes only `config google sync probe`, `push`, and `calc`.
  Calc's specialised schema-to-sheet transport is not a general substrate pull.
- The storage-provider protocol, profile binding, factory, and capability gate
  are live, stable parent surfaces. The missing SQL coordinator and general pull
  are not parent features to revive by implication.

## Considered options

1. **Recreate the local SQL sidecar and coordinator.** Rejected: it duplicates
   manifest lineage comparison, creates a second derived state authority, and
   opens destructive remote-resolution paths with no approved operator contract.
2. **Adopt the remote ciphertext-manifest boundary.** Accepted: it records the
   working safe mirror, keeps local writes remote-free, and makes integrity and
   conflict observations explicit.
3. **Add a local cache now.** Rejected: no demonstrated query or performance
   requirement justifies cache invalidation, rebuild, and authority complexity.

## Constraints

- `SecureObjectRepository.save()` and `load()` never call a remote provider;
  Drive outages cannot block local tax-data writes.
- Provider payloads are ciphertext only. The local master key, plaintext
  secure-object content, and decrypted labels never leave the workstation.
- `_sync-state` is remote, versioned integrity evidence. It is not a local SQL
  sidecar, a second write authority, or a source from which local data may be
  silently adopted.
- A namespace revision conflict blocks that namespace's push. Partial or stale
  observations remain explicit diagnostics; a successful manifest is withheld
  after an object-upload failure.
- General restore, pull, orphan adoption, status, claim, force-overwrite, and
  remote-to-local resolution are out of scope. They require an approved ADR and
  an explicit evidence, authority, and operator-safety contract.

## Implementation

The substrate-mirror flow reads raw secure-object rows, derives a namespaced
remote object identity from their existing HMAC-backed keys, and uploads the
on-wire ciphertext through `StorageProvider`. It builds one
`RemoteMirrorNamespaceManifest` per namespace under `_sync-state`; each entry
carries object identity, classification, schema version, ciphertext hash, and
storage-revision lineage. The metadata enables comparison of missing objects,
stale ancestry, and divergent revisions without decrypting a row.

`config google sync push` first compares each locally-derived manifest to the
remote manifest and verifies remote readability. It blocks a conflicting
namespace, uploads only cleared namespaces, withholds a namespace manifest when
any object upload fails, then performs post-upload and post-download inspection.
`--limit` is inspection-only: a non-dry-run limited operation is refused because
it cannot produce a complete namespace manifest. `probe` remains the provider
health surface, and `calc` remains its separately scoped transport subtree.

The current namespace-derived filename label is intentionally non-decrypting.
No `NamespaceLabelDeriver` registry is introduced. Any future human-readable
labelling proposal must prove that it neither decrypts remote-bound data nor
leaks sensitive content.

## Rationale

The remote-manifest design uses the storage revision lineage already carried by
raw secure-object rows instead of persisting parallel last-seen IDs, Drive file
IDs, hashes, and statuses locally. It therefore has one local authority and one
remote integrity observation, rather than two derived state systems that can
contradict one another. Its preflight refusal and integrity checks preserve the
ciphertext-only boundary while describing exactly what the operator can run
today. The accepted research records both the old/new comparison and the absent
general command surfaces.

## Consequences

- The obsolete migration, `DriveSync`, sync-state records, label registry, and
  general command matrix are retired design instructions; they are not backlog
  to implement.
- The Google OAuth plan must be reconciled at row level against this decision;
  this ADR does not mark any plan step complete or claim a restore workflow.
- Routine pushes enumerate current local rows and validate remote manifests;
  they do not gain the old sidecar's unchanged-row shortcut.
- A future cache is allowed only as derived, rebuildable state with a separately
  approved owner and invalidation contract.
- Escrow and cross-machine recovery remain unimplemented. Their future decision
  must reconcile the existing snapshot ADR with this manifest boundary before
  exposing an operator command.
