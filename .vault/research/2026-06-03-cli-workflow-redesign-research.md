---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---

# `cli-workflow-redesign` research: `BucketMaintenanceService authority reconciliation`

Discovery pass triggered by the W77.P370.S2131 implementation attempt. The
2026-05-15 amendment to the bucket ADR locks six methods on a new
`BucketMaintenanceService`: `browse`, `search`, `export`, `import`, `rename`,
`delete`. Implementing the service against the codebase as-is surfaced a real
hexagonal-design risk: every method except `search` already has a partial or
full authoritative primitive somewhere in the application or adapter layer, and
a naive re-implementation inside `BucketMaintenanceService` would duplicate
write paths, shadow lifecycle events, and bypass the single-writer guarantees
the existing primitives carry.

This research maps each method to its existing authority (if any), records the
top-level re-export status, names the shadowing risk, and recommends the
composition pattern the ADR addendum must lock so the service is a thin
delegator, not a parallel implementation.

## Findings

### `rename(bucket_id, new_display_name)`

Authoritative primitive: `ProfileRepository.rename(profile_id, new_label)` at
`src/aeat/application/user_profile/_profile_repository.py:415`. This is the
sole writer of the cross-store label mutation: it updates the encrypted
`UserProfileRecord.display_name` and the plaintext bucket manifest `label` in
one atomic unit of work. A thin orchestration coordinator
`rename_profile(profile_id, new_label, ...)` at
`src/aeat/application/user_profile/_orchestration.py:612` delegates to the
repository and is re-exported in `src/aeat/application/user_profile/__init__.py`
`__all__`. The lifecycle service path emits `PROFILE_RENAMED` per
`src/aeat/application/user_profile/_lifecycle.py:226`.

Shadowing risk: HIGH. Bucket `label` and profile `display_name` cannot diverge
under the existing code path, so a `BucketMaintenanceService.rename` that
re-implements either side is a duplicate writer. The two-write atomicity is
held inside `ProfileRepository.rename`; any new caller that bypasses it
re-introduces the torn-write risk the repository contract eliminates.

Recommended reconciliation: **delegate-and-extend**. The service method calls
the top-level re-export `rename_profile` for the cross-store write and then
emits `BUCKET_RENAMED` from the same call site so the bucket-maintenance audit
trail records the operator's verb invocation alongside the lifecycle event the
repository already emits. The two events are intentionally co-emitted: the
lifecycle event records the data change; the maintenance event records the
operator's surface.

### `delete(bucket_id, confirmed=False)`

Authoritative primitives split soft tombstone from hard directory removal.
Soft: `ProfileRepository.delete(profile_id)` at
`src/aeat/application/user_profile/_profile_repository.py:477` clears the
active-profile pointer, writes the manifest lifecycle status, and tombstones
the encrypted record in a single bucket session. The lifecycle service
`ProfileLifecycleService.remove` at
`src/aeat/application/user_profile/_lifecycle.py:180` emits
`PROFILE_TOMBSTONED`. The application orchestrator
`delete_profile_with_lifecycle_span(profile_id)` at
`src/aeat/application/user_profile/_orchestration.py:313` is the top-level
re-export. Hard: `remove_profile_bucket_directory(profile_id)` at
`src/aeat/application/user_profile/_orchestration.py:410` trash-renames then
recursively deletes the bucket directory.

Shadowing risk: MEDIUM-HIGH. The two-step soft-then-hard pattern is the
existing contract; the bucket ADR amendment's `delete(confirmed=True)` is the
operator-facing composition of both steps. Any `BucketMaintenanceService.delete`
that re-implements either tombstone or directory removal duplicates these
single-writer paths.

Recommended reconciliation: **compose-existing-authorities-with-cli-guards**.
The service composes the two existing primitives in sequence: tombstone via
`delete_profile_with_lifecycle_span`, then hard-erase via
`remove_profile_bucket_directory`. The `confirmed=True` service-level refusal
and the active-bucket guard (the ADR forbids deleting the active profile
bucket) live at the service boundary so the CLI `--yes` flag passes the
operator's explicit confirmation through to the same contract a programmatic
caller would observe. `BUCKET_DELETED` is emitted after the hard removal
completes; `PROFILE_TOMBSTONED` is still emitted from the inner service.

### `export(bucket_id, output_path)`

Authoritative primitives exist at application and adapter layers but no
operator entrypoint composes them. The application-layer serialiser
`serialize_profile_bundle(bucket_id)` at
`src/aeat/application/user_profile/_bundle.py:45` reads the profile record and
all four financial-history categories (work units, ledger transactions,
calculation revisions, filing records) from the bucket's encrypted
repositories and assembles them into a `UserProfilePortableExport`
(`src/aeat/domain/user_profile/_portable_export.py:28`). The adapter-layer
`ExportArchiveHeader` at
`src/aeat/adapters/persistence/storage/bucket/_export_header.py:25` provides
the plaintext frontmatter contract (bucket_id, manifest_digest,
recovery_wrap_present, archive_schema_version, created_at). Neither symbol is
currently re-exported at the application package `__all__`.

Shadowing risk: LOW. No competing implementation exists. The risk is that
`BucketMaintenanceService.export` would re-derive bundle assembly (the
walk-the-bucket-and-collect-everything logic) inline, bypassing the
domain-validated `UserProfilePortableExport` contract.

Recommended reconciliation: **compose-existing-authorities-promote-to-export**.
`BucketMaintenanceService.export` calls `serialize_profile_bundle`, wraps the
result with `ExportArchiveHeader`, writes the sealed archive to `output_path`,
emits `BUCKET_EXPORTED`. A precondition for this: promote
`serialize_profile_bundle` and `UserProfilePortableExport` to the application
package `__all__` so the service consumes them through the top-level
re-export, not through an internal-submodule import.

### `import(source_path, force_replace=False)`

Authoritative primitive: `deserialize_profile_bundle(bundle, target_bucket_id)`
at `src/aeat/application/user_profile/_bundle.py:93`. Validates
`bundle_schema_version` against the frozen `SUPPORTED_BUNDLE_SCHEMA_VERSIONS`
set declared on the same module, then writes work units, ledger transactions,
calculation revisions, and filing records via the per-category repository save
paths. Not re-exported at the package `__all__`.

Shadowing risk: LOW. Same shape as `export` — the deserialise contract is in
place; only the entrypoint composition is missing.

Recommended reconciliation: **compose-existing-authority-promote-to-export**.
Service reads the sealed archive, validates the `ExportArchiveHeader`, parses
the JSON bundle, runs the two-tier collision guard (live-profile-id and
bucket-id collision; refuse unless `force_replace=True`), provisions the
target bucket, calls `deserialize_profile_bundle`, emits `BUCKET_IMPORTED`.
Promote `deserialize_profile_bundle` and `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` to
the application package `__all__`.

### `browse(bucket_id, namespace_filter=None, cursor=None)`

Authoritative primitives are foundational repository methods on
`SecureObjectRepository` at `src/aeat/adapters/persistence/storage/sql/secure_objects.py`:
`list_namespaces()` (line 688), `list_keys(namespace)` (line 920),
`list_records(namespace, ...)` (line 937, paginated), and
`peek_metadata(namespace, object_key)` (line 1534, plaintext metadata without
decryption). The redaction policy is carried by `SensitivityClass` at
`src/aeat/core/classification.py`. None of these primitives is re-exported
through the application layer; they are adapter-layer building blocks.

Shadowing risk: LOW. No competing browse surface exists.

Recommended reconciliation: **compose-existing-authority-add-redaction-layer**.
Service resolves the per-bucket `SecureObjectRepository` (via the existing
`secure_object_repository_for_active_bucket` factory pattern), composes
`list_namespaces` + `list_keys` + `peek_metadata` per namespace, applies
`SensitivityClass` redaction so callers see only namespaces and keys their
session authorises, paginates with a cursor. The redaction layer lives at the
service boundary so the repository methods retain their foundational
adapter-layer scope.

### `search(query, scope=None)`

No authoritative primitive. The codebase contains no payload-search surface,
no full-text or attribute-search infrastructure. `search` is the only verb in
the ADR amendment without prior authority.

Reconciliation: **dedicated-design**. The verb cannot land without a separate
search-scoping ADR addressing query syntax (literal substring vs key:value
attribute match vs payload content), search scope (namespace-filtered vs
across-bucket), result ranking (recency vs classification vs match position),
decryption cost (payload search requires decrypting envelopes), and redaction
policy (`SensitivityClass` filter on results). Defer the implementation Step
until the search ADR lands.

## Implementation-authority verification

`BucketMaintenanceService` does not exist anywhere in the codebase. The only
reference is in `src/aeat/entrypoints/cli/test_ledger_verb_spine.py:227` which
pins the pre-landing state of `bucket_app` to its current single verb
(`history`) so the implementer is forced to update the expected roster when
the maintenance verbs mount.

The plan claim `W77.P371.S2136 - Migrate any legacy archive or browse callers
to BucketMaintenanceService` was structurally vacuous: there were no legacy
`archive` or `browse` callers to migrate (the `aeat archive` root was already
removed per the bucket ADR, and the bundle infrastructure was application-
layer-only with no CLI entrypoint). The Step ticked without observable code
change. Recording this as a structural-honesty finding for the campaign-close
review.

## Cross-cutting design rules surfaced

1. The service MUST consume every cross-store mutation primitive through the
   top-level application-package re-export (`from aeat.application.user_profile
   import rename_profile, delete_profile_with_lifecycle_span,
   remove_profile_bucket_directory`), never through an internal submodule
   import. Two symbols currently lack the re-export and MUST be promoted:
   `serialize_profile_bundle` and `deserialize_profile_bundle` (with
   `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` and `UserProfilePortableExport`).

2. Every bucket-maintenance event uses an existing closed enum: the
   `BucketEventType` values `BUCKET_RENAMED`, `BUCKET_DELETED`,
   `BUCKET_EXPORTED`, `BUCKET_IMPORTED` already exist at
   `src/aeat/domain/buckets/_event.py:100-103`. The `BucketEventObjectType`
   enum at the same module lacks a `BUCKET` value; emitting any of the four
   bucket-maintenance events requires either adding `BUCKET = "bucket"` to
   that closed catalogue (preferred) or reusing the existing `PROFILE` value
   (acceptable when the bucket-vs-profile distinction is purely an audit
   refinement).

3. Errors raised by the service MUST descend from `AeatError` and carry a
   declared `ErrorCode` registry entry, per the existing
   `bind_error_code __init_subclass__` discipline at
   `src/aeat/core/errors/__init__.py`. The error classes live near the service
   but the catalogue entry lands in `src/aeat/core/errors/_registry.py` so the
   service-side declaration cannot ship before the registry-side entry, per
   the audit Finding 1 from `2026-06-03-cross-domain-continuity-audit.md`.

4. The service MUST NOT introduce a new SecureObjectRepository factory or
   bucket-session helper; it consumes the existing
   `secure_object_repository_for_active_bucket` / `runtime_repository` shape
   peer agents are actively hardening under `secure-storage-production-
   hardening`. Re-deriving session resolution inside the service shadows
   peer-active work.

## Steps blocked by this research

The plan rows `W77.P370.S2131` (service implementation), `W77.P370.S2132`
(Pydantic command + result contracts and destructive-op `--yes` guards), and
`W77.P373.S2145` (service-contract tests) cannot land cleanly until the ADR
addendum below codifies the composition pattern. Once that addendum is
accepted the implementation cadence is per-verb: each verb is one atomic
explicit-path commit that lands the service method, the contract pair, the
test, the event emission, and (for `delete`) the CLI-guard wiring. The
`search` verb is split out as a separate ADR + plan Step so the other five
verbs can land while the search design proceeds.
