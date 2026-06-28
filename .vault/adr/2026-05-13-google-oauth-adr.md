---
tags:
  - '#adr'
  - '#google-oauth'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-google-oauth-adr]]"
  - "[[2026-05-08-google-oauth-adr]]"
  - "[[2026-05-06-google-oauth-research]]"
  - "[[2026-05-06-secure-persistence-enforcement-adr]]"
---

# `google-oauth` adr: `Drive bucket hierarchy, naming, atomicity, and sync state` | (**status:** `accepted`)

## Problem Statement

ADR-1 fixed the `StorageProvider` Protocol, its placement, sync-invocation model, identity contract, I/O contract, error model, probe contract, and enumeration contract. ADR-2 closes the concrete operational shape on top of that abstraction for the Google Drive backend specifically: the folder layout inside `aeat-vault/`, the surface form of filenames, per-operation atomicity, the local sync-state sidecar schema, the remote-side change-detection model, and conflict resolution for the substrate-mirror bucket. The metadata channel — what travels in Drive `appProperties` versus on disk — is settled here too, folded into the atomicity model.

ADR-2 is consumed by ADR-3 (snapshot + encryption boundary), ADR-4 (incoming bucket ingestion), ADR-5 (per-domain export taxonomy), and ADR-6 (calc → Sheets visualisation).

## Considerations

Decisions framed by:

- ADR-1 (`[[2026-05-12-google-oauth-adr]]`) — Protocol shape, beside-repository placement, `(namespace, HMAC(object_key))` identity, `bytes` I/O, typed error hierarchy, structured probe, `iter_namespaces` + `iter_objects` enumeration.
- ADR-0 (`[[2026-05-08-google-oauth-adr]]`) — operator-supplied OAuth client; per-AEAT-profile session model; SecureObjectRepository as the storage of all OAuth-side secrets.
- Research stream R3 (in `[[2026-05-06-google-oauth-research]]`) — Drive bucket layout patterns, file-ID identity model, atomic-per-call semantics, push-vs-poll change detection, conflict-resolution patterns from FreeFileSync / rclone / Sheetgo / Sync2Sheets.
- Project-wide pydantic mandate and teardown-and-rebuild stance — codified in §Constraints.

## Constraints

- **Pydantic v2 strict.** Every record / schema / manifest / boundary-crossing structure introduced by this ADR is a pydantic v2 `BaseModel` with `model_config = ConfigDict(strict=True, frozen=True, extra="forbid")`.
- **No partial implementations.** Every behaviour described in §Implementation has a complete implementation in v1. No `NotImplementedError` placeholders, no `pytest.skip`. Capabilities not implemented are not exposed.
- **No backwards-compatibility surfaces.** The Drive folder layout introduced here is the only layout; no migration shim from any prior shape; no acceptance of legacy locations.
- **Synchronous-only.** All sync-coordinator operations are synchronous, matching ADR-1's Protocol.
- **Local writes never block on Drive.** Per ADR-1 D2, the sync layer sits beside `SecureObjectRepository`; ADR-2 does not change that. The sync-state sidecar table is a local SQL table; updates are local-only on the substrate's write path.

## Implementation

### 1. Top-level folder layout — substrate namespaces at root + underscore-prefixed operator buckets

Drive layout under the operator's `aeat-vault/` root folder:

```
/aeat-vault/
  <namespace-1>/                  ← substrate-mirrored; sync coordinator writes; operator read-only
  <namespace-2>/
  ...
  _inbound/                       ← operator drops files; app reads + ingests (ADR-4)
    pending/
    processed/
    rejected/
  _workspace/                     ← read-write from both; calc-to-Sheets exports (ADR-6)
  _probe/                         ← provider health-probe sentinels
  _sync-state/                    ← internal sync metadata snapshots; operator never touches
```

Substrate namespaces appear directly at root. Operator-facing concerns live under `_`-prefixed folders. The `_` prefix is a documented convention; an operator-facing `README.md` lives at `/aeat-vault/README.md` explaining the layout.

Drive nesting depth limit is 100; v1 layout occupies 3 levels at maximum (`/aeat-vault/<namespace>/<file>` for mirrored objects; `/aeat-vault/_inbound/pending/<file>` for inbound). Comfortable margin.

### 2. Filename surface form — `<hmac_prefix_8>--<label>.<ext>` for substrate-mirror

Identity is `(namespace, HMAC(object_key))` per ADR-1 D4. The operator-visible filename in Drive UI is the hybrid:

```
{hmac_prefix_8}--{label}.{ext}
```

- `hmac_prefix_8` — first 8 hex chars of the HMAC digest. 32-bit prefix; collision probability negligible at ≤10k records per namespace.
- `label` — human-readable, filesystem-safe, derived per-namespace via the `NamespaceLabelDeriver` Protocol (§3 below). Lowercased, dashes for separators, no special characters.
- `ext` — `.bin` for raw ciphertext (default); ADR-3 may register alternate extensions for snapshot-shaped records.

Example: `a1b2c3d4--ledger-tx-2026-q1.bin` for a ledger transaction record. The four source kinds — `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice` — each occupy a distinct substrate namespace and therefore a distinct Drive folder per the cli-workflow-redesign invoice-domain-decoupling ADR; the label deriver per namespace emits a kind-appropriate human prefix.

If the label changes (the underlying domain logic updates how it names a record), the sync coordinator renames the Drive file at next push. Identity stays anchored in `appProperties.object_key_hmac` (§4), so renames are non-destructive.

### 3. Per-namespace label derivation

```python
class NamespaceLabelDeriver(Protocol):
    """Returns a human-readable, filesystem-safe label for a record."""

    def label_for(self, *, namespace: str, decrypted_payload: bytes) -> str: ...
```

Registered per namespace via a module-level registry under `src/aeat/adapters/outbound/storage/_labels.py`. Domains register their deriver during package import (ADR-5 specifies which domains register which derivers). The default deriver — for any unregistered namespace — returns `<namespace>-<short_hmac>` so even un-labelled namespaces produce browsable filenames.

Filesystem-safe rules: lowercase ASCII, digits, hyphens; max length 80 characters; multiple hyphens collapsed; leading/trailing hyphens stripped.

### 4. Per-operation atomicity — Drive `appProperties` as commit log

Every mirrored record file in Drive carries `appProperties`:

```python
class DriveAppProperties(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    namespace: str
    object_key_hmac: str            # hex; identity anchor (filename may drift)
    local_revision: int             # substrate's auto-increment SecureObjectRow.id at sync time
    classification: SensitivityClass
    synced_at: datetime
    schema_version: int             # the substrate record's schema_version at sync time
```

`appProperties` max size is 30 KB per app per file. The structure above is ≤500 bytes per record — comfortable margin.

The file's binary content is the encrypted payload from `SecureObjectRow.payload`. The `appProperties` is the commit log: drift detection during `iter_objects` enumeration compares `appProperties.local_revision` against the sync-state's `last_local_revision` to determine whether a record was committed but the local sync-state row failed to update (crash mid-push).

Atomicity per operation:

| Operation | API call | Atomic |
|---|---|---|
| Create | `files().create(media=ciphertext, body={..., appProperties: ...})` | Yes — single call |
| Update | `files().update(fileId=fid, media=ciphertext, body={appProperties: ...})` | Yes — atomic content + metadata replacement |
| Rename (label drift) | `files().patch(fileId=fid, body={name: new_name})` | Yes — metadata-only |
| Move (namespace change) | `files().patch(fileId=fid, body={parents: [new_folder_id]})` | Yes |
| Delete | `files().delete(fileId=fid)` | Yes — moves to Drive trash |

Drive has no transactions across multiple files. The sync coordinator processes one record at a time; multi-record sync runs are not atomic but each individual record is.

Crash recovery: next sync run re-enumerates Drive, observes `appProperties.local_revision` directly, and reconciles sync-state without re-uploading content.

### 5. Sync-state sidecar table

New SQL table introduced by migration `0005_secure_objects_sync_state.py`:

```sql
CREATE TABLE secure_objects_sync_state (
    namespace                 TEXT NOT NULL,
    object_key_hmac           BLOB NOT NULL,
    provider_kind             TEXT NOT NULL,         -- e.g. 'google_drive'
    drive_file_id             TEXT NOT NULL,
    drive_parent_folder_id    TEXT NOT NULL,
    last_local_content_sha256 BLOB NOT NULL,         -- SHA-256 of ciphertext at last push
    last_remote_revision      TEXT NOT NULL,         -- Drive headRevisionId at last push
    last_local_revision       INTEGER NOT NULL,      -- SecureObjectRow.id at last push
    status                    TEXT NOT NULL,         -- enum: synced/pending_push/pending_pull/conflict/tombstoned
    last_synced_at            DATETIME NOT NULL,
    PRIMARY KEY (namespace, object_key_hmac, provider_kind)
);
CREATE INDEX idx_sync_state_status ON secure_objects_sync_state(status);
CREATE INDEX idx_sync_state_provider ON secure_objects_sync_state(provider_kind);
```

The `provider_kind` column in the PK admits a future second provider (S3, B2, NextCloud) syncing the same records side-by-side without schema changes.

`secure_objects` table is unchanged. Sync state is fully separate per the secure-persistence-enforcement ADR's principle that the substrate table is the source of truth and sync layers are derived.

The pydantic record carried by the application layer for sync-state rows:

```python
class SyncStateRow(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    namespace: str
    object_key_hmac: bytes
    provider_kind: ProviderKind
    drive_file_id: str
    drive_parent_folder_id: str
    last_local_content_sha256: bytes
    last_remote_revision: str
    last_local_revision: int
    status: SyncStateStatus
    last_synced_at: datetime
```

```python
class SyncStateStatus(StrEnum):
    SYNCED = "synced"
    PENDING_PUSH = "pending_push"
    PENDING_PULL = "pending_pull"
    CONFLICT = "conflict"
    TOMBSTONED = "tombstoned"
```

### 6. Remote-side change detection — full enumeration per sync run

`aeat config google sync {push|pull|status}` invokes the coordinator which calls `iter_objects(namespace)` for every namespace in scope. No incremental `changes.list(pageToken)` API; no daemon; no in-process pageToken state.

Algorithm:

1. Coordinator calls `provider.iter_namespaces()` to learn what's on Drive.
2. For each namespace in scope (`--namespace` filter or all), coordinator calls `provider.iter_objects(namespace)` and builds a set of `(object_key_hmac, ProviderObjectMetadata)`.
3. Coordinator queries `secure_objects_sync_state` for matching rows and `secure_objects` for matching substrate rows.
4. Joins three views into a per-record classification:
   - **In substrate, in sync-state, in Drive, matching revisions** → unchanged; skip.
   - **In substrate, in sync-state, in Drive, local SHA-256 differs from `last_local_content_sha256`** → drift; push side action.
   - **In substrate, in sync-state, in Drive, Drive `headRevisionId` differs from `last_remote_revision`** → conflict (per §7).
   - **In substrate, not in sync-state** → fresh record; push.
   - **Not in substrate, in sync-state, in Drive** → operator deleted locally; tombstone-and-delete on push.
   - **Not in substrate, in sync-state, not in Drive** → both gone; sweep sync-state row.
   - **In substrate, in sync-state, not in Drive** → ghost; re-create on push.
   - **Not in substrate, not in sync-state, in Drive** → orphan; log; do nothing on push; ingestion candidate on pull.
5. Apply per-class actions (push or pull or status-render depending on invocation).

At v1 scale (≤10k records lifetime; per-namespace ≤2k typical), full enumeration costs ~`ceil(N/100)` `files.list` API calls per namespace per sync run. Bounded, well within Drive free-tier quota.

### 7. Conflict resolution for substrate-mirror bucket — refuse-on-conflict

When step 4's classification produces `conflict` (Drive `headRevisionId` differs from sync-state's `last_remote_revision`), the operator has edited or replaced the file in Drive UI or another tool has. The coordinator refuses to write that record on the current `push` invocation. Push proceeds for non-conflicting records in the same namespace; conflict-marked records are reported with `(namespace, hmac_prefix, label)` plus exit code 3 (distinct from generic error 2).

Operator resolves via three flag-driven strategies:

```
aeat config google sync push --force --resolve local  --keys <hmac_prefix_list>
aeat config google sync push --force --resolve remote --keys <hmac_prefix_list>
aeat config google sync push --force --resolve fork   --keys <hmac_prefix_list>
```

- `local` → overwrite Drive with substrate state. Operator's Drive edit discarded; logged to observability sink.
- `remote` → pull Drive content into substrate (replaces local row). Future pushes proceed from the pulled state. Substrate edit history preserves the prior revision.
- `fork` → keep both. Substrate stays put. The Drive file is renamed `<original>--operator-fork-<iso_timestamp>.<ext>`, its `appProperties.object_key_hmac` is cleared (so it stops claiming to be the mirror of that key), and it becomes an orphan from sync-state's perspective. Operator manages the fork manually thereafter.

`--keys` may be omitted to scope to all conflicting records in the active namespace filter.

**Orphan policy** (Drive file present, no matching sync-state row): logged; left alone on `push`; on `pull`, files with valid `appProperties.namespace` + `.object_key_hmac` are ingested into substrate (treated as cross-machine bootstrap). Files without those properties are logged and skipped (not app-produced).

**Ghost policy** (sync-state row exists, Drive file missing): substrate-present → re-create on next push (status reset to `pending_push`); substrate-absent too → both sides agreed on deletion; sync-state row marked `tombstoned`, swept on next push.

### 8. CLI surface

The sync-coordinator commands introduced by ADR-1 are concrete here:

```
aeat config google sync push    [--profile <id>] [--batch] [--dry-run] [--namespace <ns>] [--force --resolve <local|remote|fork>] [--keys <hmac_prefix_list>]
aeat config google sync pull    [--profile <id>] [--batch] [--dry-run] [--namespace <ns>]
aeat config google sync status  [--profile <id>] [--format json|text] [--namespace <ns>]
aeat config google sync orphans [--profile <id>] [--format json|text]
aeat config google sync claim   --file-id <drive_id> [--profile <id>]
```

`orphans` lists Drive-side orphans (files without matching sync-state). `claim` lets the operator adopt an orphan into sync-state (writes a sync-state row, runs reconciliation).

### 9. Out of scope (deferred)

- Snapshot-blob semantics, encryption boundary (ciphertext-vs-plaintext layer sync), KEK escrow for cross-machine restore — ADR-3.
- Concrete inbound ingestion semantics under `_inbound/` (move-to-processed mechanics, dedup, validation gates, operator-facing error sidecars) — ADR-4.
- Per-domain export taxonomy and the `NamespaceLabelDeriver` registrations — ADR-5.
- The contents and shape of records written under `_workspace/` (calc-to-Sheets visualisation files) — ADR-6.
- Two-way edit reconciliation for `_workspace/` files — ADR-7.

## Rationale

**Substrate namespaces at root + `_`-prefixed operator buckets.** A two-level bucket split (mirror vs operator) would either nest substrate namespaces deeper than necessary or force a `mirror/<namespace>/<file>` path that doesn't read naturally to an operator browsing Drive. Substrate namespaces directly at root gives an operator scanning `aeat-vault/` the immediate "these folders correspond to your tax data" mental model; underscore-prefixed siblings clearly signal "operator interaction zone, not substrate-mirrored." The `_` convention is small, documented at `/aeat-vault/README.md`, and matches well-known filesystem conventions (`_drafts/` in static-site generators, `_temp/` in many tools).

**Hybrid `<hmac_prefix_8>--<label>.<ext>` filenames.** R3 converged on this exact pattern. Pure HMAC hex (no label) makes operator browsing hostile — they can't tell one record from another. Pure human-readable names break Drive's "files can share names" foot-gun. Hybrid prefix-plus-label gives operator-recognisable filenames while keeping HMAC identity anchored in `appProperties` (not the filename). 32-bit prefix collision rate at our scale is structurally negligible.

**`appProperties` as commit log, not a separate sidecar JSON file.** Sidecar `.meta.json` files would double every record's Drive footprint (two files per record), making folder listings noisier and doubling the API call count for enumeration. `appProperties` (30 KB per app per file) accommodates everything we need with room to spare and surfaces in `iter_objects` returns via `files().list` with `fields="files(id,name,appProperties,...)"` in a single API call.

**Standard 9-column sync-state sidecar table.** A minimal 5-column table (just identity + drive_file_id + last_synced_at) couldn't detect local-side drift without reading Drive on every push. Adding `last_local_content_sha256` lets the coordinator skip records whose content hasn't changed since last push, dramatically reducing the API call count on routine syncs. `provider_kind` in the PK admits a future second backend without schema change.

**Full enumeration per sync run instead of incremental change feed.** Drive's `changes.list(pageToken)` is the right scale-up answer (≥100k records, sub-minute polling) but the wrong v1 answer. At ≤10k records, full enumeration is ≤100 API calls per namespace per sync. The simplicity dividend is large: no pageToken state, no token-expiry edge cases, no client-side filtering of cross-Drive changes, orphan detection comes for free, every sync run is self-contained. Incremental can be added as an amendment when scale demands; the current architecture doesn't preclude it.

**Refuse-on-conflict over last-write-wins or interactive resolution.** Industry tools for financial-data sync (Sheetgo, Sync2Sheets, TaxDome) converge on refuse + explicit operator action. Last-write-wins silently corrupts audit trails — unacceptable for tax data. Interactive prompts don't compose with `--batch` mode. Three-way merge of pydantic records doesn't generalise to encrypted PDF attachments. Refuse + three explicit resolution flags (`local` / `remote` / `fork`) covers every real intent without silent data loss.

## Consequences

**Positive.**

- Operator browsing Drive sees substrate namespaces directly + clearly-marked operator buckets; mental model is unified between substrate and Drive views.
- Hybrid filenames are Drive-searchable, operator-recognisable, and identity-stable.
- `appProperties` commit log makes crash recovery automatic and verifiable from Drive truth alone.
- Sync-state SHA-256 drift detection skips unchanged records, keeping routine sync API call counts low.
- Per-call atomicity composes with refuse-on-conflict to give legally-binding-data-safe semantics without daemon complexity.
- The orphan / ghost / conflict / drift classification is deterministic and tested through the full-enumeration algorithm.

**Negative.**

- `NamespaceLabelDeriver` is a small new abstraction; every domain that participates in sync must register one (ADR-5 enumerates registrations). Domains without a deriver fall back to `<namespace>-<short_hmac>` — browsable but uninformative.
- Full enumeration on every sync invocation pays network cost even when nothing changed remotely. Bounded at v1 scale but not asymptotically optimal.
- Refuse-on-conflict requires operator-visible UX for resolution; the `--force --resolve <strategy>` flag matrix is one more thing operators must learn. CLI help text and the operator-facing README must explain the three strategies.
- Two SQL tables in the storage substrate (`secure_objects` + `secure_objects_sync_state`); both governed by the secure-persistence-policy test.
- Drive nesting depth used: 3 levels for mirrored files (`aeat-vault/<namespace>/<file>`), 3 for inbound subbuckets (`aeat-vault/_inbound/pending/<file>`). Well within the 100-level cap but not absolutely minimal; deeper nested namespaces in the substrate (if any future domain introduces them) get translated into Drive-side flat folder names (`namespace.sub.deep/` as one folder) to avoid depth explosion.

**Neutral.**

- The `_` convention for operator-facing buckets is ours; documented at `/aeat-vault/README.md` and in operator-facing help text. Risk of operator confusion is low because the README sits in the bucket itself.
- Sync-state table grows linearly with the substrate; expected size at v1 scale is ≤10k rows × ~200 bytes = ≤2 MB. Negligible.
- Conflict resolution flags are advisory until operator passes `--force`; the default `push` is always safe (no destructive overwrites without explicit consent).

## References

External:
- Drive API folder hierarchy + parent semantics — `https://developers.google.com/drive/api/guides/folder`
- Drive API `appProperties` reference — `https://developers.google.com/workspace/drive/api/guides/properties`
- Drive API file `update` and `patch` atomicity — `https://developers.google.com/workspace/drive/api/reference/rest/v3/files/update`
- Drive duplicate-file gotcha (community) — `https://github.com/rclone/rclone/issues/4412`
- Conflict resolution patterns survey (Sheetgo, Airtable, Sync2Sheets) — drawn from R5 / R6 of the OAuth research stream.

Internal:
- `[[2026-05-12-google-oauth-adr]]` — Protocol shape and placement.
- `[[2026-05-08-google-oauth-adr]]` — OAuth + per-profile session model.
- `[[2026-05-06-google-oauth-research]]` — bucket hierarchy / atomicity / sync-state research.
- `[[2026-05-06-secure-persistence-enforcement-adr]]` — substrate this sidecar table extends.
