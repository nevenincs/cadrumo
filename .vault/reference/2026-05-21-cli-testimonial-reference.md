---
tags:
  - '#reference'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-20-cli-state-architecture-research]]"
---

# profile-state-storage-reference

Exhaustive storage map for a PROFILE entity. Every physical location, key
function, and name-as-identity coupling is documented here to support the
ADR that will replace human-chosen name as stable identity with a generated
UUID.

---

## 1. Bucket directory layout

File: `src/aeat/adapters/persistence/storage/bucket/_layout.py`

The root of every bucket is `<aeat_local_storage_root>/buckets/<bucket_id>/`.

Constants (lines 24-27):

```
_BUCKETS_DIRNAME = "buckets"
_DB_DIRNAME      = "db"
_BLOBS_DIRNAME   = "blobs"
_AUDIT_DIRNAME   = "audit"
```

`BucketPaths` (line 30) carries:
- `bucket_id: str` — the directory name, currently equals the human-chosen profile name
- `root: Path`
- `bucket_dir: Path` — `<root>/buckets/<bucket_id>/`
- `db_dir: Path` — `<root>/buckets/<bucket_id>/db/`
- `blobs_dir: Path` — `<root>/buckets/<bucket_id>/blobs/`
- `audit_dir: Path` — `<root>/buckets/<bucket_id>/audit/`

`bucket_paths(root, bucket_id)` at line 43 resolves paths without IO.
`provision_bucket_directory(root, bucket_id)` at line 73 materialises the
tree and is fail-closed (`FileExistsError` if the directory already exists).

The master-key keystore lives at the sibling path
`<root>/keystore/<bucket_id>/` (`_keystore_paths.py:34`).

Active-profile pointer file: `<root>/active-profile` (plaintext TOML, section 4).

---

## 2. The manifest

File: `src/aeat/adapters/persistence/storage/bucket/_manifest.py`

`BucketManifest` (line 82) fields:

| Field | Type | Notes |
|---|---|---|
| `bucket_id` | `str` | Directory name = profile name today |
| `label` | `str` | Display label (set to `profile_id` in `_orchestration.py:314`) |
| `created_at` | `datetime` | UTC |
| `last_unlocked_at` | `datetime \| None` | UTC |
| `kdf_params` | `ManifestKdfParams` | Argon2id params + salt |
| `recovery_enrolled` | `bool` | |
| `schema_version` | `int` | |

IO: `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`

- `manifest_path(paths)` → `<bucket_dir>/manifest.toml` (line 24)
- `write_manifest(paths, manifest)` — atomic write-then-rename (line 86)
- `read_manifest(paths)` — strict-validate on load (line 102)

The manifest is the existence claim used by `_profile_bucket_scan.py` and
`_orchestration.py`. A manifest-only bucket is treated as a real registered
profile even if the encrypted `UserProfileRecord` is absent.

---

## 3. Per-bucket secure-objects store

File: `src/aeat/application/user_profile/_repository.py`

### SecureObjectRepository binding

`_secure_objects_for_bucket(bucket_id)` at line 37 constructs a
`SecureObjectRepository` bound to:

```
sqlite:///<aeat_local_storage_root>/buckets/<bucket_id>/db/aeat.db
```

This is `BucketPaths.db_dir / "aeat.db"`. The engine is created via
`create_engine_from_settings(Settings(aeat_database_url=...))`.

### Secure-object key functions

`user_profile_value_object_key(bucket_id, profile_id)` at line 84:

```python
return f"user-profile:{trimmed_bucket}:{trimmed_profile}"
```

Today `bucket_id == profile_id` so an example key is
`"user-profile:carmen:carmen"`. Any rename or directory move makes the record
unaddressable.

`user_profile_snapshot_object_key(bucket_id, snapshot_id)` at line 96:

```python
return f"user-profile-snapshot:{trimmed_bucket}:{trimmed_snapshot}"
```

### Namespaces in `db/aeat.db`

| Constant | Value | Line |
|---|---|---|
| `USER_PROFILE_VALUE_NAMESPACE` | `"aeat.application.user_profile.value"` | 31 |
| `USER_PROFILE_SNAPSHOT_NAMESPACE` | `"aeat.application.user_profile.snapshot"` | 32 |

`WorkflowState` is stored in the same per-bucket SQLite:
- Namespace `"aeat.workflow"` / key `"state"` (`_persistence.py:35-36`)

`WorkflowResult` runs:
- Namespace `"aeat.application.workflow.runs"` / key `run_id` (`_persistence.py:37`)

All of these live in the same `db/aeat.db` file for the active bucket.

---

## 4. The active-profile pointer

Files:
- `src/aeat/core/_bucket_pointer.py` — `BucketPointer` model
- `src/aeat/core/_bucket_pointer_io.py` — IO helpers

Pointer file path: `<aeat_local_storage_root>/active-profile`
(`_POINTER_FILENAME = "active-profile"` at `_bucket_pointer_io.py:18`).

On-disk TOML shape:

```toml
bucket_id = "<profile-name>"
schema_version = 1
```

The `bucket_id` field stores the human-chosen profile name.

IO functions in `_bucket_pointer_io.py`:

- `pointer_path(root)` → `<root>/active-profile` (line 21)
- `read_pointer(root)` → `BucketPointer | None` (line 27)
- `write_pointer(root, pointer)` — atomic write-then-rename (line 88)
- `resolve_active_bucket_id()` (line 48) — canonical resolver; precedence:
  1. `Settings.aeat_active_profile` (env `AEAT_ACTIVE_PROFILE` or `--profile` flag)
  2. `<root>/active-profile` pointer file

Write sites in orchestration:
- `_write_active_profile_pointer(bucket_id)` at `_orchestration.py:95` — called
  by `register_active_profile` (line 182) and `select_profile` (line 353)
- `_clear_active_profile_pointer()` at `_orchestration.py:114` — called by
  `remove_active_profile`

---

## 5. Manifest-scan computed view (profile enumeration)

File: `src/aeat/application/workflow/_profile_bucket_scan.py`

`WorkflowState.profiles` was retired. Profile enumeration is now a filesystem scan.

`read_profile_bucket(profile_name, *, root)` at line 28:
- Resolves `<root>/buckets/<profile_name>/manifest.toml`
- Returns `ProfileBucketPointer(bucket_id=profile_name)` when manifest is present
- Returns `None` when absent; never opens any encrypted database

`list_profile_buckets(*, root)` at line 56:
- Scans `<root>/buckets/*/manifest.toml`
- Returns `dict[str, ProfileBucketPointer]` keyed by profile name (= directory name)

`ProfileBucketPointer` (`_models.py:109`) carries `bucket_id: str` which
today equals the profile name. The docstring at line 11 explicitly states:
"Under the 1:1 cardinality the bucket id equals the profile id, so the
returned ProfileBucketPointer simply records the profile name as the
bucket id."

---

## 6. WorkflowState

File: `src/aeat/application/workflow/_models.py`

`WorkflowState` (line 130) is a frozen pydantic model persisted via
`WorkflowStateRepository` into `db/aeat.db` of the active bucket. Fields:

| Field | Type |
|---|---|
| `auth` | `AuthState` |
| `declarations` | `dict[str, DeclaracionPointer]` |
| `invoice_reviews` | `dict[str, InvoiceReviewRecord]` |
| `ledger_reviews` | `dict[str, LedgerReviewRecord]` |
| `bucket_events` | `tuple[WorkflowEvent, ...]` |
| `updated_at` | `datetime` |

The historical `profiles` field is retired (docstring line 148).

`WorkflowStateRepository` (`_persistence.py:48`) uses
`SecureObjectRepository()` which resolves its engine from
`Settings.aeat_database_url` derived from `resolve_active_bucket_id()`. No
explicit `bucket_id` injection; entirely driven by the active-profile pointer.
Secure-object key: namespace `"aeat.workflow"`, object_key `"state"`.

`WorkflowState.active_profile_record()` (line 163) calls
`resolve_active_bucket_id()` then `service.read(bucket_id)` — the read key
and the directory name are the same value today.

---

## 7. Lifecycle service

File: `src/aeat/application/user_profile/_lifecycle.py`

`ProfileLifecycleService` (line 60):

| Method | Line | Notes |
|---|---|---|
| `register` | 76 | Creates `UserProfileRecord`; saves via `user_profile_value_object_key` |
| `read` | 110 | Loads by `user_profile_value_object_key(bucket_id, profile_id)` |
| `list_profiles` | 115 | Iterates `iter_records()` on the repository |
| `edit_field` | 134 | Upserts one fact; saves under same key |
| `edit_section` | 159 | Bulk-replaces a section |
| `remove` | 175 | Tombstones the record; does NOT delete directory |
| `rename` | 188 | Saves under new key (line 227); deletes old key (line 228); does NOT rename directory |
| `duplicate` | 237 | Copies record under new `profile_id` key |

`rename` at line 188 is the critical site: it renames the secure-object key
but leaves the bucket directory named after the original profile. After
`rename("carmen", "carmen-2025")` the directory is `buckets/carmen/` but the
secure-object key inside it is `user-profile:carmen:carmen-2025`. The manifest
`bucket_id` still says `"carmen"`. This is the ghost-profile / broken-record
defect from the research document.

`RenameProfileCommand` (`__init__.py:124`): `source_profile_id`, `target_profile_id`, `target_display_name | None`.

Factory `build_lifecycle_service(*, bucket_id, ...)` at `_orchestration.py:59`.

Orchestration key facts (`_orchestration.py`):
- Docstring line 9-12: `"Bucket identity convention: bucket_id == profile_id"` — the explicit statement of the 1:1 conflation
- `register_active_profile` (line 141): 5-step atomic-create sequence
- `_ensure_profile_bucket_manifest` (line 301): writes `BucketManifest(bucket_id=profile_id, label=profile_id)` — both fields set to the human name

---

## 8. Token / auth-lock directory

Config field `Settings.aeat_token_dir` at `src/aeat/core/config.py:123`:

```python
aeat_token_dir: Path = Field(
    default=PROJECT_ROOT / ".tokens",
    ...
)
```

Default is `<project_root>/.tokens/` — outside `AEAT_LOCAL_STORAGE_ROOT`.
This is the "state scattered across independently-rooted locations" defect
from the research document.

Auth session file naming (profile name = `bucket_id` embedded as filename prefix):

| Provider | Pattern | Source |
|---|---|---|
| Certificate | `<bucket_id>-storage.json` | `auth/_authenticator.py:1092` |
| Cl@ve Móvil | `<bucket_id>-clave-movil-storage.json` | `auth/_clave_movil.py:648` |
| Generic sessions | `<bucket_id>-{stem}.json` | `auth/_sessions.py:108` |
| Browser factory | `<bucket_id>-storage.json` | `browser/_factory.py:126` |

Auth acquisition lock naming (`auth/_acquisition_lock.py:79`):

```python
settings.aeat_token_dir / f"{require_active_bucket_id()}-{kind.value}-auth.lock"
```

All five patterns embed `require_active_bucket_id()` (= the profile name) directly
as a filename prefix. Renaming a profile orphans every one of these files.

---

## 9. Every place the profile NAME is used as a stable id / bucket_id

### Core identity coupling

| File | Line | Pattern |
|---|---|---|
| `bucket/_layout.py` | 62 | `bucket_dir = root / _BUCKETS_DIRNAME / bucket_id` — directory IS named by id |
| `bucket/_manifest.py` | 91 | `BucketManifest.bucket_id` stored in TOML |
| `bucket/_manifest_io.py` | 59 | Serialised as `bucket_id = "..."` |
| `user_profile/_repository.py` | 93 | `f"user-profile:{trimmed_bucket}:{trimmed_profile}"` secure-object key |
| `user_profile/_repository.py` | 105 | `f"user-profile-snapshot:{trimmed_bucket}:{trimmed_snapshot}"` snapshot key |
| `core/_bucket_pointer.py` | 30 | `BucketPointer.bucket_id` stores name |
| `core/_bucket_pointer_io.py` | 48-84 | `resolve_active_bucket_id()` returns name from pointer |

### Orchestration (name-as-id propagation)

| File | Line | Pattern |
|---|---|---|
| `user_profile/_orchestration.py` | 9-12 | Docstring: `"bucket_id == profile_id"` |
| `user_profile/_orchestration.py` | 171 | `build_lifecycle_service(bucket_id=profile_id)` |
| `user_profile/_orchestration.py` | 281 | `bucket_paths(root, profile_id).bucket_dir` |
| `user_profile/_orchestration.py` | 314 | `BucketManifest(bucket_id=profile_id, label=profile_id)` |
| `user_profile/_orchestration.py` | 347 | `build_lifecycle_service(bucket_id=profile_id)` in `select_profile` |
| `user_profile/_orchestration.py` | 434 | `service.read(bucket_id)` — profile_id used as read key |

### Profile scan

| File | Line | Pattern |
|---|---|---|
| `workflow/_profile_bucket_scan.py` | 53 | `ProfileBucketPointer(bucket_id=profile_name)` |
| `workflow/_profile_bucket_scan.py` | 82 | `result[entry.name] = ProfileBucketPointer(bucket_id=entry.name)` |

### Workflow state / models

| File | Line | Pattern |
|---|---|---|
| `workflow/_models.py` | 168 | `"bucket id and profile name are 1:1 by orchestration convention"` |
| `workflow/_models.py` | 178 | `service.read(bucket_id)` — bucket_id treated as profile read key |
| `workflow/_persistence.py` | 56 | `SecureObjectRepository()` resolves engine via active profile pointer (name) |

### Auth token/lock filenames

| File | Line | Pattern |
|---|---|---|
| `auth/_authenticator.py` | 1092 | `aeat_token_dir / f"{require_active_bucket_id()}-storage.json"` |
| `auth/_clave_movil.py` | 648 | `token_dir / f"{profile}-clave-movil-storage.json"` |
| `auth/_sessions.py` | 108 | `aeat_token_dir / f"{require_active_bucket_id()}-{stem}.json"` |
| `auth/_acquisition_lock.py` | 79 | `aeat_token_dir / f"{require_active_bucket_id()}-{kind.value}-auth.lock"` |
| `browser/_factory.py` | 126 | `aeat_token_dir / f"{profile_name}-storage.json"` |

### CLI entrypoints

| File | Lines | Pattern |
|---|---|---|
| `cli/_config/__init__.py` | 245, 270, 284, 468, 522, 571 | `resolve_active_bucket_id()` used as `profile_id` directly |
| `cli/_config/__init__.py` | 489, 558 | `_read_profile_record(profile_id=..., bucket_id=...)` both set to same name |

---

## 10. All readers of profile state

### `overview` (`aeat app overview`)

`src/aeat/application/overview/__init__.py` — loads `WorkflowState` via
`workflow_state_repository().load()`. Accesses `TransactionCatalogueRepository`,
`InvoiceCatalogueRepository`, `ModeloDraftRepository` — all bucket-scoped via
`resolve_active_bucket_id()`.

### `auth status` / `auth test`

Both call `resolve_active_bucket_id()` and read `WorkflowState.auth`. The
research document notes these two paths read different store subsets, producing
disagreeing answers about the active profile.

### `profile show` / `status` / `list`

`src/aeat/entrypoints/cli/_config/__init__.py`:
- `profile list`: `list_profile_buckets()` (manifest scan, no decryption) then
  `_read_profile_record(profile_id, bucket_id)` for each entry
- `profile show` (lines 466-474): `read_profile_bucket(name)` →
  `build_lifecycle_service(bucket_id=bucket_id).read(profile_id)`

### `assess_active_profile_health`

`src/aeat/application/workflow/_profile_health.py:60` — reads five stores in
sequence: env/settings → pointer file → manifest scan → `WorkflowState`
(encrypted) → lifecycle service read. Called by diagnostics, repair, and
overview status surfaces.

### Workflow engine (`verify`, `modelo readiness`)

`src/aeat/application/workflow/_engine.py` — builds `WorkflowState` via
repository; calls `state.active_profile_record()` which resolves the profile
record through the lifecycle service via `resolve_active_bucket_id()`.

---

## 11. Migration surface

### On-disk layout for an existing named-bucket install

```
<aeat_local_storage_root>/
  active-profile                    # TOML: bucket_id = "<profile-name>"
  buckets/
    <profile-name>/                 # directory named by human name
      manifest.toml                 # bucket_id = "<profile-name>", label = "<profile-name>"
      db/
        aeat.db                     # SQLite secure_objects rows:
                                    #   namespace "aeat.application.user_profile.value"
                                    #     key "user-profile:<name>:<name>"
                                    #   namespace "aeat.application.user_profile.snapshot"
                                    #     key "user-profile-snapshot:<name>:<snap-id>"
                                    #   namespace "aeat.workflow" / key "state"
                                    #   namespace "aeat.application.workflow.runs" / key <run_id>
      blobs/
      audit/
  keystore/
    <profile-name>/                 # master-key material
<project_root>/.tokens/             # OUTSIDE storage root
  <profile-name>-storage.json
  <profile-name>-clave-movil-storage.json
  <profile-name>-<kind>-auth.lock
```

### Per-profile steps a UUID migration must perform

1. Generate `uuid4` as `stable_id`; retain human name as `display_name`
2. Rename `buckets/<name>/` → `buckets/<uuid>/`
3. Rename `keystore/<name>/` → `keystore/<uuid>/`
4. Rewrite manifest: `bucket_id = "<uuid>"`, `label = "<name>"` (display stays)
5. Rekey secure-object rows in `db/aeat.db` (single SQLite transaction):
   - `"user-profile:<name>:<name>"` → `"user-profile:<uuid>:<uuid>"`
   - `"user-profile-snapshot:<name>:<snap>"` → `"user-profile-snapshot:<uuid>:<snap>"`
   - Workflow state and run rows are not name-keyed; they do not need rekeying
6. Rewrite active-profile pointer: `bucket_id = "<uuid>"`
7. Rename token files: `<name>-storage.json` → `<uuid>-storage.json` etc. (best-effort)
8. Delete or ignore lock files (TTL expiry handles stale locks)

Steps 2-6 are not natively atomic. A recommended transaction boundary: do step 5
inside SQLite first (fully transactional), then steps 2-4 and 6 as filesystem
operations. A failed filesystem rename after a successful DB rekey leaves a
known degraded state (UUID keys in a name-named directory) that a re-run of the
migration can detect and finish.

---

## UUID-cutover blast-radius summary

Ranked by migration risk and breadth of change:

1. **`user_profile_value_object_key` / `user_profile_snapshot_object_key`** (`_repository.py:84,96`) — format strings embed `bucket_id`; every on-disk row is unreadable without in-place SQLite rekeying before any code update
2. **Bucket directory path** (`_layout.py:62`) — the directory name IS the `bucket_id`; every derived path (`db/`, `blobs/`, `audit/`, keystore) is stale after rename; this is the blast radius of all `BucketPaths` consumers
3. **`BucketManifest.bucket_id`** (`_manifest.py:91`) — persisted in TOML; must be rewritten atomically with directory rename
4. **`BucketPointer.bucket_id`** (`_bucket_pointer.py:30`) — the active-profile pointer stores the name; must be rewritten
5. **Auth token/lock filenames** (5 sites in `auth/` and `browser/`) — all embed `require_active_bucket_id()` as filename prefix; existing files orphaned unless renamed; missing files force re-authentication (not data loss)
6. **`_profile_bucket_scan.py`** (lines 28, 53, 56, 82) — scanner uses `entry.name` (directory name) as `bucket_id`; after UUID rename the directory carries no display information; must be changed to read UUID from manifest
7. **Orchestration 1:1 convention** (`_orchestration.py:9-12, 171, 314, 347`) — `bucket_id == profile_id` assumption must be broken; the two become independent fields with separate lifecycle
8. **`WorkflowState.active_profile_record()`** (`_models.py:178`) — calls `service.read(bucket_id)` passing UUID; profile records stored under name-based key are unreachable until SQLite rows are rekeyed (dependency on item 1)
9. **`_secure_objects_for_bucket(bucket_id)`** (`_repository.py:37-65`) — constructs database URL from `bucket_id`; must use UUID after directory rename
10. **Keystore path** (`_keystore_paths.py:34`) — `keystore_path(root, bucket_id)` returns `<root>/keystore/<bucket_id>/`; requires same rename as bucket directory (item 2)

---

## Migration considerations

- **Pre-migration inventory:** call `list_profile_buckets()` to enumerate every
  bucket directory; read each manifest for the display name; generate a stable
  UUID per bucket; write a durable mapping `old_name → uuid` before any
  mutation starts.

- **Safe migration sequence:** (a) generate UUID, (b) rekey DB rows in a single
  SQLite transaction (fully reversible), (c) rewrite manifest `bucket_id`,
  (d) rename bucket and keystore directories (not transactional — these are
  the atomicity gap), (e) rewrite pointer, (f) rename token files best-effort.

- **Token-file rename is best-effort.** A missing renamed file forces
  re-authentication on the next CLI invocation; it is not data loss.

- **Lock files** can be deleted rather than renamed; the TTL expiry already
  handles stale locks.

- **No backward-compatible dual-key read path is feasible** within a single
  process. The migration must be a one-time forward migration. A
  `aeat config migrate-profile-uuid` command executed once per install is the
  lowest-risk delivery vehicle.

- **`aeat_token_dir`** defaults to `<project_root>/.tokens/` outside
  `AEAT_LOCAL_STORAGE_ROOT`. A UUID migration could optionally relocate
  token files under the storage root to close the state-isolation defect
  identified in the research document; this should be a separate decision
  in the ADR rather than bundled silently into the UUID migration.
