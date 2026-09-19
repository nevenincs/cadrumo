---
tags:
  - '#research'
  - '#google-oauth'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:ddec8b7fa3279ae7f12264dd9fc76b953e0b0a9ccc19a016946c9f574310b5dd'
related:
  - "[[2026-06-05-secure-storage-production-hardening-w12-p26-s379-review-audit]]"
  - "[[2026-07-12-google-oauth-audit]]"
  - '[[2026-07-12-google-oauth-adr]]'
---

# `google-oauth` research: `P03 sync-state re-planning`

This research determines whether P03's open local-SQL sync-state design remains the
right next step after the currently shipped ciphertext mirror and remote-manifest
implementation.

## Findings

### The planned and current designs are materially different

P03 and the accepted Drive-sync ADR prescribe a derived local
`secure_objects_sync_state` table, a `DriveSync` coordinator, per-record Drive file
and revision state, full enumeration, and explicit `push`, `pull`, `status`,
`orphans`, and `claim` commands. The table is the planned comparison baseline for
drift, tombstones, ghosts, and conflict resolution. Evidence:
`file:.vault/plan/2026-05-13-google-oauth-plan.md:136-159` and
`file:.vault/adr/2026-05-13-google-oauth-adr.md:126-235`.

The current path has no migration, `SyncStateRow`, `DriveSync`, label-deriver
registry, or local sync-state repository. An exact source search on 2026-07-12 found
none of those symbols under `src/` or `migrations/`. Instead,
`SecureObjectRepository.iter_all_records_raw()` yields encrypted on-wire payloads
together with revision lineage, without decrypting them:
`file:src/aeat/adapters/persistence/storage/sql/secure_objects.py:291-365`.

For each namespace, the current mirror builds a remote manifest in `_sync-state` from
that raw ciphertext state. The manifest records HMAC-keyed object identity, ciphertext
hash, storage revision, predecessor revision, ancestry, and write times; it does not
carry decrypted domain payloads. It compares local and remote manifests for missing
objects, stale ancestry, and divergent revisions:
`file:src/aeat/adapters/outbound/storage/_mirror_manifest.py:34-59`,
`file:src/aeat/adapters/outbound/storage/_mirror_manifest.py:115-212`, and
`file:src/aeat/adapters/outbound/storage/_mirror_manifest.py:248-340`.

`google_sync_push` calculates the expected manifest from the active secure-object
repository, blocks a namespace on a revision conflict, uploads ciphertext only, and
withholds its manifest when an object upload fails. It then verifies upload and
download integrity before reporting the outcome:
`file:src/aeat/entrypoints/cli/_config/_google.py:537-750` and
`file:src/aeat/entrypoints/cli/_config/_google.py:797-911`. This keeps Drive off the
local write path, consistent with the accepted storage-provider ADR:
`file:.vault/adr/2026-05-12-google-oauth-adr.md:51-72`.

The live `aeat config google sync --help` command on 2026-07-12 exposes only
`probe`, `push`, and `calc`. P03's general `pull`, `status`, `orphans`, and `claim`
surfaces are absent. Consequently the current implementation is a safe remote mirror,
not evidence that P03's complete bidirectional coordinator was delivered. The
foundation-reconciliation audit reaches the same restraint:
`file:.vault/audit/2026-07-12-google-oauth-audit.md:39-49`.

### Options

1. **Restore the original local SQL coordinator.** Add the migration, derived table,
   coordinator, label derivation, and original command matrix exactly as P03 specifies.
   This creates a second state model alongside the manifest that the live mirror already
   uses, duplicates revision comparison, and widens the persistence and destructive
   conflict-resolution blast radius.
2. **Adopt the remote-manifest mirror as the successor design (recommended).** Retain
   the secure-object store as source of truth and derive expected state from raw rows at
   push time. Treat the remote namespace manifest as integrity and lineage evidence,
   not as a local write-path sidecar. Preserve conflict refusal and the ciphertext-only
   boundary. Do not imply that this provides restore, general pull, orphan adoption, or
   remote overwrite resolution.
3. **Add a local cache later only for a demonstrated need.** A cache could support a
   future performance or operator-workflow requirement, but it must be explicitly
   rebuildable from the secure-object repository and remote manifests. It is not needed
   to maintain the current push safety guarantees.

### Recommendation and ADR disposition

Author a **new replacement ADR** before changing P03 status or implementing another
sync surface. An amendment is too weak: the accepted Drive-sync ADR requires a local
SQL sidecar and a `DriveSync` command model that are absent, while the working code
uses remote manifests and revision lineage instead. The replacement should explicitly
supersede the prior ADR's local sidecar, coordinator, label-derivation, and general
command-matrix decisions.

The ADR should bind these points:

- `SecureObjectRepository` remains the only local authority; mirror code consumes its
  raw ciphertext rows and never adds remote I/O to `save()` or `load()`.
- `_sync-state` holds one remote, versioned integrity manifest per namespace; it is not
  a local SQL synchronization table or a second write authority.
- The preflight comparison and post-upload/download inspections are the current
  refusal and verification contract. A revision conflict blocks the affected namespace;
  partial/stale observations remain explicit diagnostics.
- `push` is the presently supported substrate-mirror operation. Restore, general pull,
  orphan adoption, status, and destructive resolution require their own approved scope
  and must not be inferred from the manifest code.
- Namespace-only filenames stay ciphertext-safe until a separately approved design can
  prove that human labels do not require decrypting payloads or leaking sensitive data.

### Blast radius

- **Vault/plan:** Reconcile P03's local-table and coordinator rows as superseded only
  after the replacement ADR is accepted; retain rows for genuinely desired but absent
  user-facing operations in a successor plan.
- **Persistence:** The recommended decision adds no Alembic migration and avoids a
  parallel state table. Any future cache needs rebuild and authority guarantees.
- **CLI:** Current `probe` and `push` remain stable. There is no shipped general
  `pull`, `status`, `orphans`, or `claim` command to deprecate; future commands need
  explicit safety and operator semantics.
- **Security and verification:** Preserve ciphertext-only remote payloads, manifest
  integrity checks, and active-profile/provider-factory composition. The production
  hardening audit independently confirms those boundaries:
  `file:.vault/audit/2026-06-05-secure-storage-production-hardening-w12-p26-s379-review-audit.md:14-33`.

## Sources

- `file:.vault/plan/2026-05-13-google-oauth-plan.md:136-159`
- `file:.vault/adr/2026-05-12-google-oauth-adr.md:51-72`
- `file:.vault/adr/2026-05-13-google-oauth-adr.md:126-257`
- `file:src/aeat/adapters/persistence/storage/sql/secure_objects.py:291-365`
- `file:src/aeat/adapters/outbound/storage/_mirror_manifest.py:34-340`
- `file:src/aeat/entrypoints/cli/_config/_google.py:537-911`
- `file:.vault/audit/2026-06-05-secure-storage-production-hardening-w12-p26-s379-review-audit.md:14-80`
- `file:.vault/audit/2026-07-12-google-oauth-audit.md:17-50`
