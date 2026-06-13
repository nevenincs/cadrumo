---
tags:
  - '#adr'
  - '#google-oauth'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-08-google-oauth-adr]]"
  - "[[2026-05-06-google-oauth-research]]"
  - "[[2026-05-06-google-oauth-audit]]"
  - "[[2026-05-06-secure-persistence-enforcement-adr]]"
---

# `google-oauth` adr: `Storage provider abstraction` | (**status:** `accepted`)

## Problem Statement

The forthcoming Google integration needs a uniform read/write surface that admits two backends initially — the local filesystem (already implicit throughout the codebase) and Google Drive (introduced by this series) — and that can admit additional providers (S3, B2, NextCloud, OneDrive, …) by adding new implementation classes without amending the surface. The substrate-side identity model (namespace × HMAC) must extend cleanly across the boundary so callers do not encounter two different identity schemes depending on which provider they are talking to.

ADR-1 defines this Protocol, its placement relative to `SecureObjectRepository`, the sync-invocation model, the identity contract, the I/O contract, the error model, the health-probe contract, and the enumeration contract. Concrete bucket layout, naming conventions, sync-state sidecar schema, atomicity per operation, and snapshot/encryption-boundary semantics are deferred to ADR-2 and ADR-3 respectively. Per-domain export taxonomy is ADR-5.

ADR-1 consumes the auth contract established in `[[2026-05-08-google-oauth-adr]]` (ADR-0). It assumes the substrate from `[[2026-05-06-secure-persistence-enforcement-adr]]` is in place.

## Considerations

Decisions framed by:

- Forward research (`[[2026-05-06-google-oauth-research]]`) — 2026 OAuth practice, library versions, and the provider-abstraction survey (fsspec / PyFilesystem2 / pydrive2 / rclone).
- Codebase audit (`[[2026-05-06-google-oauth-audit]]`) — the post-teardown state of `src/aeat/adapters/outbound/google/` and the substrate-side enumeration gaps.
- Secure-persistence substrate (`[[2026-05-06-secure-persistence-enforcement-adr]]`) — landed encrypted SQL substrate with envelope encryption, classification-aware records, and the existing `_rotation.py` external-iteration pattern that this ADR mirrors.
- Project-wide pydantic mandate — every data record / schema / manifest / boundary-crossing structure is a pydantic v2 BaseModel with strict validation. Non-negotiable; codified in §Constraints.
- Project-wide teardown-and-rebuild stance — no deprecation shims, no migration helpers, no partial implementations, no references to removed surfaces. Codified in §Constraints.

## Constraints

- **Pydantic v2 strict mandate.** Every record / schema / manifest / boundary-crossing structure introduced by this ADR is a pydantic v2 `BaseModel` with `model_config = ConfigDict(strict=True, frozen=True, extra="forbid")`. Non-frozen models are permitted only where the type carries mutable state by design; this ADR introduces no such type.
- **No partial implementations.** Every Protocol method has a complete implementation in both v1 backends (`LocalFileSystemProvider` and `GoogleDriveProvider`). No `NotImplementedError` placeholders, no `pytest.skip("not yet implemented")` markers. Capabilities not implemented in v1 are not exposed on the Protocol at all and are not stubbed.
- **No backwards-compatibility surfaces.** The Protocol replaces no prior surface; there is no shim to a previous identity scheme. The CLI commands introduced by ADR-0 (`aeat config google ...`) are the only entry point.
- **Synchronous-only.** The Protocol is synchronous. No async methods. Composes with the substrate's synchronous SQLAlchemy 2.0 calls.
- **Local writes never block on a remote provider.** Per §Implementation §2, the provider sits beside `SecureObjectRepository`; nothing in the local hot read/write path makes a network call.
- **Single canonical OAuth flow inherited from ADR-0.** Drive backend authenticates exclusively via the per-profile `oauth-token` record from the substrate. No alternate credential sources.

## Implementation

### 1. Protocol — custom thin shape over native primitives

`StorageProvider` is a `@runtime_checkable` Protocol defined under `src/aeat/adapters/outbound/storage/_protocol.py`. The local backend (`_local.py`) uses `pathlib` and standard-library I/O directly. The Drive backend (`_google_drive.py`) uses `google-api-python-client` directly. No fsspec, no PyFilesystem2, no pydrive2, no rclone. Library survey rationale lives in `[[2026-05-06-google-oauth-research]]`.

The Protocol is provider-agnostic. A future S3 / B2 / NextCloud provider implements the same Protocol without amending its shape; the addition arrives as a separate ADR amendment introducing a new implementation class.

### 2. Placement — beside `SecureObjectRepository`

The provider is consumed by a `DriveSync` coordinator that lives at `src/aeat/application/storage/sync/`. The coordinator iterates `SecureObjectRepository` externally (via the new `iter_namespaces()` + `iter_all_records_raw()` substrate methods called for in `[[2026-05-06-google-oauth-research]]`) and pushes/pulls via the provider. Nothing inside `SecureObjectRepository.save()` or `load()` calls the provider; the substrate's hot path stays SQL-only.

This mirrors the structural idiom of the substrate's existing `_rotation.py` (rotates DEKs by iterating records externally). It also isolates provider-side failures: when Drive is unreachable, the local substrate continues to operate; only the next `aeat config google sync` invocation surfaces the failure.

### 3. Sync invocation — explicit operator commands

```
aeat config google sync push   [--profile <id>] [--batch] [--dry-run] [--namespace <ns>]
aeat config google sync pull   [--profile <id>] [--batch] [--dry-run] [--namespace <ns>]
aeat config google sync status [--profile <id>] [--format json|text]
```

- `push` mirrors local → provider (writes new/changed records; deletes tombstoned per ADR-2's sync-state).
- `pull` mirrors provider → local (cross-machine bootstrap; selective recovery).
- `status` reports drift between local and remote (rows pending push, rows newer remotely, conflicts).
- `--namespace` scopes to a single namespace.
- `--dry-run` reports the diff without executing.
- `--batch` suppresses prompts, emits JSON output, returns exit codes for OS-scheduler integration (cron / Task Scheduler / launchd).

No daemon. No in-process scheduler. Operator chooses cadence either by manual invocation or by wiring `--batch` invocations into their OS scheduler. Project takes no position on cadence.

### 4. Identity — `(namespace, HMAC(object_key))` composite

Every object the Protocol handles is identified by a composite key matching the substrate's existing `SecureObjectRow` identity: `(namespace: str, object_key_hmac: bytes)`. Identity is structurally collision-free under a fixed namespace, removing the Drive "files-can-share-names" foot-gun at the Protocol layer.

Human-readable surface form of the filename on Drive (whether the file appears as `<hmac_hex>.bin` or `<hmac_prefix>--<label>.bin` or some other shape) is metadata, not identity. ADR-2 owns that choice.

### 5. I/O contract — `bytes` in / `bytes` out

`put_object` accepts `bytes`. `get_object` returns `bytes`. Provider implementations stream internally (Drive uses `MediaIoBaseDownload` with chunked transfer; Local reads in one syscall) but expose a synchronous bytes API. Matches the substrate's bytes-everywhere contract.

Materialisation to on-disk paths for libraries that demand real files (`pdfplumber.open`, `openpyxl.load_workbook`, etc.) is the existing `src/aeat/adapters/persistence/storage/blob_store/_materialisation.py` layer's job. Not the Protocol's concern.

### 6. Error model — typed hierarchy rooted at `AeatError`

```
StorageError(AeatError)
├─ StorageNotFoundError
├─ StorageConflictError
├─ StoragePermissionError
├─ StorageQuotaError              (carries retry_after: float | None)
├─ StorageNetworkError
├─ StorageIntegrityError          (carries expected: str, actual: str)
└─ StorageUnavailableError
```

Each subclass is a pydantic-validated frozen record carrying its own structured fields. The CLI layer catches `AeatError` at the top boundary and renders structured messages. Providers translate native errors (`googleapiclient.errors.HttpError`, `OSError` family, etc.) into the typed hierarchy at the Protocol boundary — callers never see native exceptions.

The hierarchy integrates with the existing error registry under `src/aeat/core/errors/`; every subclass is registered so the registry-coverage test catches new exception classes that fail to register.

### 7. Health probe — structured report

```python
class ProviderProbeReport(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    reachable: bool
    read_ok: bool
    write_ok: bool
    delete_ok: bool
    quota_remaining_bytes: int | None = None
    errors: tuple[StorageError, ...] = ()
```

`StorageProvider.probe(*, read_only: bool = False) -> ProviderProbeReport` exercises read/write/delete against a designated probe location (Drive: a sentinel file under `aeat-vault/_probe/`; Local: a `_probe/` directory under the configured root). `read_only=True` skips write and delete; only `reachable` and `read_ok` are populated. `aeat config google sync status` is a thin renderer over `probe()`.

### 8. Enumeration — `iter_namespaces()` + `iter_objects(namespace)`

```python
class ProviderObjectMetadata(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    namespace: str
    object_key_hmac: str            # hex digest, matches substrate identity
    size_bytes: int
    modified_at: datetime
    provider_revision: str          # opaque revision / etag / version

class StorageProvider(Protocol):
    def iter_namespaces(self) -> Iterator[str]: ...
    def iter_objects(self, namespace: str) -> Iterator[ProviderObjectMetadata]: ...
```

Symmetric with the substrate-side enumeration introduced in ADR-3 (`SecureObjectRepository.iter_namespaces()` + `iter_all_records_raw()`). Same shape on both sides means drift computation is set-diff at the namespace level and set-diff per-namespace at the object level. Generator-backed; memory-bounded for large namespaces.

### 9. Configuration and instantiation

Providers are instantiated per-profile by a factory:

```python
def get_storage_provider(*, kind: ProviderKind, settings: Settings, profile_id: str) -> StorageProvider:
    ...
```

`ProviderKind` is a `StrEnum` with `LOCAL` and `GOOGLE_DRIVE` v1 members. The factory:

- For `LOCAL`: returns a `LocalFileSystemProvider` rooted at `settings.aeat_export_dir / profile_id` (a new setting introduced by this ADR — defaults to `<project>/var/exports/<profile_id>/`).
- For `GOOGLE_DRIVE`: loads the per-profile OAuth credentials from `SecureObjectRepository` (per ADR-0's `aeat:google:profile:{profile_id}:oauth-token` namespace), constructs `googleapiclient.discovery.build("drive", "v3", credentials=creds)` and `build("sheets", "v4", credentials=creds)`, and returns a `GoogleDriveProvider`.

A future provider amendment registers an additional `ProviderKind` member and a factory branch.

### 10. Test strategy

Per the project's no-mocks mandate:

- **Unit tests** colocated with the implementation files (`_test_protocol.py`, `_test_local.py`, `_test_google_drive.py`) construct real provider instances against `tmp_path` (Local) or an in-memory fake Google Drive backend (introduced by this ADR under `src/aeat/adapters/outbound/storage/_testing.py` as a real `InMemoryDriveProvider` implementing the same Protocol).
- **Live tests** under `_test_google_drive_live.py` are gated by `AEAT_LIVE_TESTS_ENABLED` and exercise the real Drive API against the operator's Cloud Console project (per ADR-0's operator-supplied OAuth client). No CI dependency on Google.
- **Substrate-policy tests** are extended: `tests/import_contract/test_adr_layout_import_smoke.py` adds `aeat.adapters.outbound.storage` to `ADR_LAYOUT_PACKAGES`; `_REQUIRED_SECURE_OBJECT_CONSUMERS` extends to cover the provider factory's credential read path.

### 11. Out of scope (deferred)

- Concrete Drive folder layout, file naming, atomicity semantics, sync-state sidecar table schema, polling cadence, conflict resolution per bucket — ADR-2.
- Snapshot semantics (per-row mirror vs whole-DB blob), encryption boundary (ciphertext-layer vs plaintext-layer sync), KEK escrow, manifest format, restore flows — ADR-3.
- Incoming-bucket ingestion patterns — ADR-4.
- Per-domain export taxonomy (which domains export, in what direction, in what format) — ADR-5.
- Calculation → Sheets visual verification surface — ADR-6.
- Two-way edit reconciliation — ADR-7.

## Rationale

**Custom thin Protocol over fsspec / pydrive2 / rclone.** Research stream R1 converged on this: Drive's file-ID identity model is fundamentally incompatible with fsspec's path-uniqueness assumption (documented duplicate-file bugs in rclone, FreeFileSync, Duplicacy forums). fsspec's transaction model is semi-atomic rather than per-call atomic. pydrive2 ships its own OAuth lifecycle that fights ADR-0's per-profile credential ownership. rclone is the right tool for a sync daemon, wrong tool for a synchronous CLI library. A ~600-LOC custom implementation is bounded, fully testable under the no-mocks mandate, and stays within the synchronous-first architecture the rest of the codebase uses.

**Beside `SecureObjectRepository` rather than above or inside.** Research stream R8 converged on this with explicit reasoning. Inside (every save() writes through to the provider) makes local writes pay Drive latency and turns Drive outages into local-write outages — unacceptable for legally-binding tax data. Above (snapshot-level only) cannot satisfy the "100% mirror of database storage hierarchy and structure" requirement the user established for the series; Drive would see opaque blobs, not the namespace hierarchy. Beside (a coordinator that iterates the repo externally) preserves local-hot-path speed, isolates provider failures, and structurally mirrors the existing `_rotation.py` pattern.

**Explicit sync commands with `--batch` over daemon or auto-sync.** Daemons are architecturally inappropriate for a CLI tool (no daemon lifecycle to attach to; cross-platform scheduling is the OS's job). Auto-sync after every local write reintroduces the "Drive failure breaks local writes" problem we just rejected. Explicit-with-batch gives operators full control for ad-hoc use and full automatability via their OS scheduler — the project ships no schedule of its own and takes no position on cadence.

**`(namespace, HMAC(object_key))` identity over string paths or opaque ObjectIds.** The substrate already uses this composite identity (`SecureObjectRow.object_key` is an HMAC digest under a namespace). Asking the Protocol to invent a different scheme creates impedance. Drive's "files-can-share-names" foot-gun disappears because HMAC under a fixed namespace folder is structurally unique. Local's "path = identity" is satisfied because the path is also `(namespace, HMAC)`. Human-readable filename surface is metadata — ADR-2's concern.

**`bytes` in / `bytes` out over file-like streams or path-or-stream.** Substrate is bytes-everywhere. At our scale (records ≤ 50 MB; total DB measured in hundreds of MB lifetime), eager bytes is not a memory problem — the cost of two return types or context-manager discipline exceeds the benefit. Materialisation to disk for libraries that demand paths stays in `_materialisation.py`, separate from the Protocol.

**Typed `StorageError` hierarchy rooted at `AeatError`.** The project already has an error-registry pattern that substrate exceptions participate in. A parallel error system would create two taxonomies that don't compose at the CLI boundary, where storage calls are intermixed with substrate calls. Same hierarchy = single `except AeatError` at the CLI top, structured logging respects redaction, registry tests catch new unregistered classes.

**Structured `ProviderProbeReport` with `read_only` flag over boolean probe or no probe.** Boolean readiness loses information that the operator needs to act on (auth issue vs permission issue vs quota issue). No probe forces every caller to re-implement put/get/delete dance. `read_only=True` handles the "operator doesn't want sentinel files in their Drive" concern.

**`iter_namespaces` + `iter_objects(namespace)` over no enumeration or per-namespace-only.** Sync coordinator needs to find drift; pull-on-fresh-workstation needs to discover what's there; ADR-4 incoming-bucket ingestion needs to enumerate what the operator dropped. Per-namespace alone can't discover unknown namespaces. Provider-wide-only loses the natural batching unit. Both together compose cleanly with the substrate-side enumeration ADR-3 mandates.

## Consequences

**Positive.**

- Hot read/write path stays SQL-only; Drive failures are isolated.
- Identity model is uniform across substrate and provider; no impedance translation in calling code.
- Pydantic-validated boundary types compose with the project's existing record-and-pipeline patterns.
- Error model integrates with the existing registry; no parallel exception hierarchy.
- Sync invocation cleanly separable into manual / batched-cron modes without changing code paths.
- Future providers (S3, B2, NextCloud, etc.) plug in by implementing the Protocol; ADR-1 surface does not change.
- Test strategy is fully under the project's no-mocks discipline (in-memory provider for unit tests; gated live tests for integration).

**Negative.**

- Two-store consistency is eventual. The operator must trigger sync (or schedule it) — there is a window between local change and Drive mirror where the two diverge.
- `DriveSync` coordinator + sync-state sidecar table = additional moving parts to maintain.
- Custom Protocol owns ~600 LOC across the two v1 implementations + factory + in-memory fake; we re-implement patterns fsspec would have given for free (chunked download, pagination, retries) at the cost of having to test them ourselves.
- The Drive backend depends on `google-api-python-client` discovery — a heavy import on every CLI invocation that touches Google. Mitigation: lazy import inside the factory branch, not at module top-level.
- `aeat_export_dir` is a new setting; one more field in `src/aeat/core/config.py` and `env/.env.example`.

**Neutral.**

- The Protocol's synchronous-only stance does not preclude a future async layer if a sync daemon were ever introduced; an async wrapper around the synchronous Protocol is straightforward.
- The in-memory `InMemoryDriveProvider` for unit tests is itself a real implementation of the Protocol — it serves both as a test fixture and as a forward-compatible reference for what a "minimum viable backend" looks like for future providers.
- The factory's per-profile instantiation composes naturally with ADR-0's per-profile OAuth session model; no new identity concept is introduced.

## References

External:
- fsspec API reference and Drive backend survey — `https://filesystem-spec.readthedocs.io/`
- pydrive2 — `https://docs.iterative.ai/PyDrive2/`
- rclone librclone — `https://github.com/rclone/rclone/tree/master/librclone/python`
- Google Drive API duplicate-file behaviour discussion — `https://github.com/rclone/rclone/issues/4412`
- "The Google Drive API doesn't know about paths" — `https://despairlabs.com/blog/posts/2013-03-22-the-google-drive-api-doesnt-know-about-paths-and-that-s-bad/`

Internal:
- `[[2026-05-08-google-oauth-adr]]` — auth contract this ADR consumes.
- `[[2026-05-06-google-oauth-research]]` — Protocol-survey research.
- `[[2026-05-06-google-oauth-audit]]` — pre-excision baseline.
- `[[2026-05-06-secure-persistence-enforcement-adr]]` — substrate contract this provider sits beside.
