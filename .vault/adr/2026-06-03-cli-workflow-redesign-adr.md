---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-cli-workflow-redesign-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-06-03-cross-domain-continuity-audit]]"
---

# `cli-workflow-redesign` adr: `BucketMaintenanceService composition pattern` | (**status:** `accepted`)

## Problem Statement

The 2026-05-15 amendment to the bucket ADR locks six methods onto a new
`BucketMaintenanceService` (`browse`, `search`, `export`, `import`, `rename`,
`delete`) and the W77 wave Steps `S2131`, `S2132`, `S2145`, `S2150`, `S2152`,
`S2153` schedule the implementation. The implementation attempt against the
codebase as-is surfaces a real hexagonal-design risk: every method except
`search` already has a partial or full authoritative primitive in the
application or adapter layer that the existing CLI tree does not yet expose.
The amendment is silent on whether `BucketMaintenanceService` is a parallel
implementation, a thin composition of the existing primitives, or a new
authority that supersedes them.

The risk of leaving this ambiguous is concrete. The cross-store label rename
already lives inside `ProfileRepository.rename`, which is the sole writer of
the encrypted-record + plaintext-manifest pair under a single bucket session.
The soft tombstone and hard directory removal already split across
`ProfileRepository.delete` / `delete_profile_with_lifecycle_span` and
`remove_profile_bucket_directory`. The portable bundle assembly and
re-hydration already live in `serialize_profile_bundle` /
`deserialize_profile_bundle` with the domain-validated
`UserProfilePortableExport` contract and a frozen
`SUPPORTED_BUNDLE_SCHEMA_VERSIONS` set. A naive `BucketMaintenanceService`
that re-implements any of these paths re-introduces the torn-write risk the
single-writer contracts eliminate and creates shadow lifecycle-event emission.

This ADR codifies the composition pattern the service MUST follow so that
landing the six methods strengthens the existing authority surface rather than
duplicating it.

## Considerations

The research document maps each of the six methods to its existing authority,
re-export status, shadowing risk, and recommended composition pattern. Five
of the six methods compose existing primitives; `search` has no prior
authority and is split out as a separate ADR scope. The composition pattern
turns on three observations.

First, the existing primitives are not isolated. `ProfileRepository.rename` is
re-exported as `rename_profile` through `aeat.application.user_profile`.
`delete_profile_with_lifecycle_span` and `remove_profile_bucket_directory`
are co-exported at the same package boundary. The bundle serialiser and
deserialiser, plus the `UserProfilePortableExport` contract and the
`SUPPORTED_BUNDLE_SCHEMA_VERSIONS` frozen set, are NOT yet re-exported and
the service MUST NOT close-fist them by importing from the internal
`_bundle` / `_portable_export` modules; the promote-to-export step is a
precondition.

Second, the bucket-maintenance event enum is already in place
(`BUCKET_RENAMED`, `BUCKET_DELETED`, `BUCKET_EXPORTED`, `BUCKET_IMPORTED`)
but the closed catalogue `BucketEventObjectType` lacks a `BUCKET` value. The
service emits the bucket-maintenance events from its own call site; the
inner primitives continue to emit their lifecycle events (`PROFILE_RENAMED`,
`PROFILE_TOMBSTONED`). Two-event co-emission per operator action is the
intended pattern: the lifecycle event records the data change; the
maintenance event records the operator's surface invocation. The single
enum-extension needed is `BUCKET = "bucket"` on `BucketEventObjectType`.

Third, the destructive-action protocol locked by the 2026-05-15 amendment
(`delete` requires `--yes` at the CLI boundary and `confirmed=True` at the
service boundary; the active profile bucket cannot be deleted until the
operator switches profiles) describes service-side refusals, not just CLI
ergonomics. The refusals MUST live at the service contract so any
programmatic caller observes the same guarantee the CLI operator does. The
CLI `--yes` flag is the operator's mechanism for passing the confirmation
through, not the source of the guarantee.

## Constraints

Two upstream surfaces remain in flight and constrain the cadence. The
`secure-storage-production-hardening` campaign is actively reshaping the
secure-object repository factory paths and runtime session contracts; the
service MUST consume the existing
`secure_object_repository_for_active_bucket` factory and the
`runtime_repository` surfaces rather than introducing a parallel session
helper. The audit-finding `bind_error_code` opacity captured in
`2026-06-03-cross-domain-continuity-audit.md` Finding 1 means any new error
class declared by the service MUST land its `ErrorCode` registry entry in
the same commit as the class declaration, or peer test runs see the
`AeatError subclass ... is missing a declared ErrorCode registry entry`
refusal until the registry entry arrives.

The `search` verb is not implementable under this ADR. Query syntax (literal
vs key:value vs payload-content), scope (namespace-filtered vs across-bucket),
ranking (recency vs classification vs match position), decryption cost
(payload search requires decrypting envelopes), and redaction policy
(`SensitivityClass` filter) are all undecided. A dedicated search ADR must
land before the search Step can open.

## Implementation

The service lives at `src/aeat/application/bucket_maintenance/` as a new
package. The package `__init__.py` exposes the service class and the
Pydantic command + result contracts; everything the operator-CLI handler
imports comes through that top-level surface. Internal modules
(`_service`, `_contracts`, `_errors`) are not consumed from outside the
package.

The service is a thin composition layer. `rename` delegates to the
top-level re-export `rename_profile` for the cross-store write, then emits
`BUCKET_RENAMED`. `delete` composes `delete_profile_with_lifecycle_span`
(soft tombstone) followed by `remove_profile_bucket_directory` (hard
removal), refusing without `confirmed=True` at the service boundary and
refusing the active bucket regardless of the confirmation flag; after the
hard removal completes, `BUCKET_DELETED` is emitted. `export` calls
`serialize_profile_bundle`, wraps the result with `ExportArchiveHeader`,
writes the sealed archive to the operator-specified path, emits
`BUCKET_EXPORTED`. `import` reads the sealed archive, validates the
`ExportArchiveHeader`, parses the JSON bundle, runs the two-tier collision
guard (live-profile-id and bucket-id collision; refuse unless
`force_replace=True`), provisions the target bucket if new, calls
`deserialize_profile_bundle`, emits `BUCKET_IMPORTED`. `browse` resolves the
active bucket `SecureObjectRepository` and composes `list_namespaces` +
per-namespace `list_keys` counts for a namespace-level inventory. Key-level
browse with `peek_metadata`, `SensitivityClass` redaction, and cursor
pagination remains follow-up work. `search` is deferred to the accepted
bucket-search ADR.

Pydantic command and result contracts (`RenameBucketCommand` /
`RenameBucketResult`, etc.) live in `_contracts.py`. They use the existing
`BucketId` core identity type from `src/aeat/core/identity.py`, the existing
`SensitivityClass` core enum for browse redaction, and the existing
`BucketEventType` / `BucketEventObjectType` closed catalogues for event
construction. The closed-set typing rule (per the architecture-boundaries
rule's "Type every constant-like axis" clause) means the contracts MUST type
every closed-value field as its enum, never as a bare string.

Three preconditions land alongside or before the per-verb implementation
Steps: (1) `BUCKET = "bucket"` is added to `BucketEventObjectType` in
`src/aeat/domain/buckets/_event.py` with a corresponding value-equality test
in `src/aeat/domain/buckets/test_event_catalogue.py`; (2)
`serialize_profile_bundle`, `deserialize_profile_bundle`,
`UserProfilePortableExport`, and `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` are
promoted to the application package `__all__`; (3) the service-side error
classes and their `ErrorCode` registry entries land in the same commit per
the audit Finding 1 discipline.

The Step ordering under W77.P370 changes accordingly. S2131 is replaced by
five per-verb implementation Steps (rename, delete, export, import, browse)
plus one preconditions Step (`BUCKET` enum + bundle re-exports + error
registry entries). S2132 keeps its contracts + destructive-guards scope but
moves under each per-verb Step's atomic commit. S2145 keeps its
service-contract test scope and is one test module per verb. The `search`
verb opens a new Step under a new Phase blocked by the search ADR.

## Rationale

The codebase already carries single-writer, atomicity-preserving primitives
for the four cross-store operations the bucket-maintenance surface needs.
Re-implementing any of them inside the service would trade a known-correct
contract for a parallel path with no verification history. The 2026-05-15
amendment was authored before the inventory of existing primitives was
established; this ADR is the reconciliation.

The two-event co-emission pattern (`PROFILE_RENAMED` plus `BUCKET_RENAMED`
on a single rename invocation) is a deliberate audit feature, not a bug.
The lifecycle event records the data change; the maintenance event records
the operator's verb. A future audit query distinguishing "the record was
relabelled" from "the operator invoked the maintenance verb" relies on the
two events being distinct.

Promoting the bundle serialiser and deserialiser to the application
package `__all__` before the service consumes them honours the durable
single-authoritative-source / no-internal-submodule-import discipline
named in the operator directive on 2026-06-03. Importing `serialize_profile_bundle`
through the package boundary is the same shape every other consumer uses;
allowing the service to bypass that and dot into `_bundle` would set a
precedent for the next caller to do the same.

## Consequences

The five composition-pattern Steps (rename, delete, export, import, browse)
become tractable single-turn landings, each as one explicit-path service
method, Pydantic contract, service-contract test, and event emission. The `search`
verb is intentionally deferred to the accepted bucket-search ADR. The
2026-06-10 operator-surface decision also retires the older `config bucket`
CLI mount, so W77.P374.S2152 closes R08 for the shipped service scope without
restoring a storage-noun operator command.

## 2026-06-12 closeout amendment - W77 service scope

The W77 closeout verified the backend/application service scope:
`BucketMaintenanceService` now ships `browse`, `rename`, `delete`, `export`,
and `import`. Export writes sealed archives through the adapter-layer archive
writer and emits `BUCKET_EXPORTED`; import reads sealed archives, enforces
schema/passphrase/collision guards, provisions missing buckets through the
profile create span, deserializes via the profile bundle service, and emits
`BUCKET_IMPORTED`.

Search remains out of scope for this ADR and is owned by the bucket-search ADR.
No `aeat config bucket` CLI mount is required or allowed for W77 closure.

The two-event co-emission per operator action increases the bucket-event
history volume (every rename writes two events, every delete writes two
events). The history is already append-only via secure-object storage; the
volume increase is proportional to operator actions and is bounded.
Downstream consumers of the bucket-event history that filter on a single
event-type are unaffected; consumers that fold rename + tombstone activity
gain a more precise signal.

The S2136 audit finding ("Migrate any legacy archive or browse callers to
BucketMaintenanceService" was structurally vacuous) is recorded in the
research doc as a structural-honesty observation for the campaign-close
review under `aeat-campaign-close-honesty-review`. The Step itself is not
re-opened; the campaign-close review surfaces the pattern so future
"migrate-existing-callers" Steps include a verification gate naming the
caller set being migrated.

The bundle-export re-export promotion has a small blast radius (four
symbols) and is independently testable; it lands as the preconditions Step
and is consumed by the export + import per-verb Steps. The
`BucketEventObjectType.BUCKET` enum addition lands in the same Step and is
covered by the existing `test_event_catalogue.py` shape.

## Codification candidates

- **Rule slug:** `service-imports-via-top-level-reexports`.
  **Rule:** A new application-layer service MUST consume cross-package
  primitives through the consumed package's top-level `__all__` re-export,
  never through an internal submodule import (the `_foo` module that owns
  the implementation is private to its package). Promote the symbol to
  `__all__` as a precondition; the service-side import line is then the
  package-top-level form.

- **Rule slug:** `composition-service-no-parallel-write-path`.
  **Rule:** When a new service exposes an operator-facing verb that
  corresponds to an existing single-writer primitive, the service MUST
  delegate the write to the existing primitive (preserving its atomicity
  and lifecycle-event emission) and MUST NOT re-implement the write path.
  The service emits its own surface-level event in addition to the
  primitive's lifecycle event; the two events are intentionally distinct.
