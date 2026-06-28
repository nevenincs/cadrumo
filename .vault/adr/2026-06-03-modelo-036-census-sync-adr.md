---
tags:
  - '#adr'
  - '#modelo-036-census-sync'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-06-03-m036-lifecycle-verbs-research]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr]]'
  - '[[2026-06-03-cli-workflow-redesign-adr]]'
  - '[[2026-06-04-modelo-036-census-sync-research]]'
---

# `modelo-036-census-sync` adr: `M036 declaration service: bucket-scoping contract` | (**status:** `accepted`)

## Problem Statement

The M036 declarative-recording verbs (`aeat app modelo m036 {alta,modificacion,baja}`) need a persistence backbone. The content-addressed helper `derive_m036_declaration_id` and the typed `M036DeclarationCommand` / `M036DeclarationResult` contracts landed in commit `e5783f5d7`; the `LIVE_M036_DECLARATION_NAMESPACE` with the bucket-scoped grammar `m036-declaration:{bucket_id}:{declaration_id}` is registered; the three `CENSO_DECLARATION_*` `BucketEventType` members exist. The open question is the contract shape between the future `M036DeclarationService` and the secure-object persistence layer: should the service consume the existing generic `SecureSnapshotRepository` (which presumes payload models carry both `bucket_id` and `snapshot_id` attributes per the `_bucket_id_of` / `_snapshot_id_of` helpers in `src/aeat/application/live/_snapshot_base.py`) by extending `M036DeclarationResult` with a `bucket_id` field, or build a parallel content-addressed repository whose bucket scope stays implicit on the active-bucket session?

## Considerations

- `SecureSnapshotRepository` is the shared persistence primitive for every bucket-scoped live snapshot service (Borrador100, Censo, Expedientes, Notifications). Its save/load/list/resolve flow already enforces classification, envelope schema-version, namespace, object-key derivation, bucket-id cross-check on read, and prefix-resolution with ambiguity errors. Re-deriving any of these in a parallel repository duplicates load-bearing invariants.
- The `composition-service-no-parallel-write-path` rule forbids a new application-layer service from re-implementing an existing single-writer primitive. A parallel `SecureDeclarationRepository` targeting the same `SecureObjectRepository` substrate with its own envelope wrapping and bucket cross-check is exactly the shadow-write-path shape the rule names.
- The `aeat-architecture-boundaries` rule mandates that domain records flow as strict, validated typed envelopes -- no `dict[str, Any]`, no bare scalars. A `bucket_id` field on `M036DeclarationResult` is a strict typed field, not a leak.
- The auth-configure flow at `src/aeat/application/auth/_operator.py` lines 250-340 resolves `active_bucket_id` once and threads it into both the `BucketEvent` (which DOES carry `bucket_id` as a typed field on the event record) and the `secure_object_repository_for_active_bucket().save_many(...)` call. The pattern is: bucket scope is resolved from session, then stamped onto the typed record. Bucket scope is not hidden ambient state; every persisted typed record carries it.
- `M036DeclarationResult` is the operator-facing return value of the verb. Operators and audit consumers reading the result of a declaration call need the bucket id to correlate the declaration with the profile bucket whose state changed. An implicit, session-only bucket scope erases that correlation at the return surface.
- The content-addressed `declaration_id` (SHA-256 over the canonical tuple) is semantically distinct from a `snapshot_id`. `SecureSnapshotRepository` already exposes object-key derivation as a `Callable` parameter precisely so a consumer can supply its own naming. Re-using the persistence-substrate `snapshot_id` attribute name as a substrate-only alias is a substrate concern, not an operator-surface concern.

## Constraints

- The `SecureSnapshotRepository` generic requires `bucket_id` and `snapshot_id` string attributes on the payload model -- enforced at runtime by `_bucket_id_of` and `_snapshot_id_of` raising `LiveApplicationInputError` when absent. The current `M036DeclarationResult` (`frozen`, `strict`, `extra=forbid`) carries `declaration_id` but not `bucket_id` and exposes no `snapshot_id` alias.
- The contracts landed in commit `e5783f5d7` with `extra=forbid`, so promoting the contract requires a coordinated commit that updates the contract and every consumer in one atomic change per the relocation-atomicity discipline in `aeat-architecture-boundaries`.
- The `service-imports-via-top-level-reexports` rule requires every symbol consumed across package boundaries to be re-exported from the consumed package top-level `__all__`. The new service will need `SecureSnapshotRepository`, `SnapshotNotFoundError`, and the registered namespace constant promoted to top-level surfaces before the service module imports them.
- The contracts have not shipped to any consumer yet; no public surface depends on the absence of `bucket_id`.

## Implementation

Decision: Path A -- extend the contract with `bucket_id` and reuse `SecureSnapshotRepository`.

The `M036DeclarationResult` Pydantic model gains a typed `bucket_id: BucketId` field (`frozen`, `strict`, `extra=forbid` preserved). The service constructs a `SecureSnapshotRepository[M036DeclarationResult]` bound to the active bucket, with `payload_model = M036DeclarationResult`, `namespace_definition = LIVE_M036_DECLARATION_NAMESPACE`, an `object_key` closure that emits `m036-declaration:{bucket_id}:{declaration_id}` (matching the registered grammar), and a dedicated `M036DeclarationNotFoundError` / `M036DeclarationAmbiguousPrefixError` pair inheriting from `SnapshotNotFoundError` so the shared error taxonomy applies.

The repository `_snapshot_id_of` helper reads the payload `snapshot_id` attribute. To bridge the naming gap without a behavioural shim, `M036DeclarationResult` declares `snapshot_id` as a read-only `@computed_field` that returns `self.declaration_id`. The operator-facing field name stays `declaration_id`; the secure-object substrate reads `snapshot_id` through the alias. This avoids both the parallel-repository shadow write path and the operator-visible rename of a content-addressed id.

The service is stateless (declarations are append-only audit records -- no supersession, no demotion); it composes `SecureSnapshotRepository.save` / `list_snapshots` / `resolve` directly without inheriting from `SnapshotService` or `StatelessSnapshotService`. The auth-configure two-event co-emission pattern is followed: the service writes the typed declaration record AND appends the matching `CENSO_DECLARATION_*` `BucketEvent` in the same `save_many` batch, preserving the two-event audit shape established in `composition-service-no-parallel-write-path`.

## Rationale

Path B (parallel repository) was rejected on three grounds:

- It duplicates the envelope-classification, schema-version, and object-key invariants that `SecureSnapshotRepository` already enforces, creating two write paths over the same `SecureObjectRepository` substrate. This is the canonical shape `composition-service-no-parallel-write-path` forbids.
- It hides bucket scope as session-ambient state on the persisted record. Every other typed record persisted through the secure-object substrate (Borrador100, Censo snapshots, Expedientes captures, `BucketEvent` itself, workflow state, profile auth record) stamps `bucket_id` onto the typed payload. A declaration record that omits it is the outlier, not the convention.
- The bucket cross-check on `SecureSnapshotRepository.load` / `save` (raising `LiveApplicationInputError` when the payload bucket disagrees with the repository) is a load-bearing safety gate against bucket-confused writes. Path B would need to re-derive an equivalent or accept the regression.

The `snapshot_id` alias-property bridges the naming gap without either renaming `declaration_id` (which would erase the content-addressing semantic at the operator surface) or muddying the secure-object substrate with payload-attribute-name dispatch. The contract extension is one strict field; the alias is one computed field; both are validated at the model boundary.

## Consequences

Pre-condition Steps (must land before the service module is authored, each per the `service-imports-via-top-level-reexports` rule and the relocation-atomicity discipline):

- PRE-1: promote `SecureSnapshotRepository`, `SnapshotNotFoundError`, and `SnapshotRepository` to the `aeat.application.live` package `__all__` (they currently live on the `_snapshot_base` private submodule). Add a regression gate test that pins these as public surface, mirroring `test_bundle_reexports.py`.
- PRE-2: promote `LIVE_M036_DECLARATION_NAMESPACE` to the `aeat.adapters.persistence.storage` package `__all__` so the service imports it through the package boundary, not by dotting into `_namespace_registry`.
- PRE-3: extend `M036DeclarationResult` with the typed `bucket_id: BucketId` field AND the `snapshot_id` computed-field alias in one atomic commit; add a round-trip-equality test under `src/aeat/application/modelo/test_m036_lifecycle.py` that asserts `M036DeclarationResult` survives a save/load cycle through a real `SecureSnapshotRepository` with strict pydantic equality, every default field populated non-default, per the `aeat-roundtrip-discipline` rule. Pair with an anti-tautology test that mutates the on-disk envelope to drop `bucket_id` and asserts reload surfaces a `ValidationError`.

3-commit landing plan (replaces the research sketch with the bucket-scoping-resolved sequence):

- Commit 1 (preconditions): PRE-1 + PRE-2 + PRE-3 bundled -- top-level re-exports for both packages, contract extension, round-trip and anti-tautology tests for the extended contract. Run `uv run --no-sync pytest --collect-only -q` clean before commit per relocation atomicity. Tag subject prefix `relocation:M036DeclarationResult`.
- Commit 2 (service): `M036DeclarationService` module with `record_alta` / `record_modificacion` / `record_baja` / `list_declarations` verbs, the `M036DeclarationNotFoundError` / `AmbiguousPrefix` error pair, and the seven service-contract tests enumerated in the research. The service composes `SecureSnapshotRepository` plus the existing `append_bucket_event` / `BucketEventHistoryRepository` pair in one `save_many` batch.
- Commit 3 (CLI mount): the `m036_app` Typer subgroup under `aeat app modelo`, the four CLI tests enumerated in the research, and the locale-catalogue keys added via `python -m aeat.locales set` for the new verb help and refusal strings across `en` / `es` / `ca` / `hu` per `aeat-locales-cli`.

Audit-trail gain: the bundled-evidence shape established for ledger-derived revisions in `ledger-derived-revisions-bundle-evidence` extends naturally to declaration records -- the bucket-id stamp ties every audit-trail declaration to the profile bucket whose census state it asserts.

No shadow write path: the secure-object substrate keeps one consumer pattern for bucket-scoped typed records.

Pitfall: the `snapshot_id` alias is invisible at the operator surface but visible to the persistence substrate. A future refactor that retires the `_snapshot_id_of` lookup in favour of an explicit `id_field` parameter on `SecureSnapshotRepository` would let the alias retire cleanly. Until then, the alias is documented on the model docstring as a substrate-bridge field, not an operator field.

## Codification candidates

- Rule slug: `bucket-scope-stamped-on-typed-record`. Rule: Every typed record persisted to a bucket-scoped secure-object namespace MUST carry the owning `bucket_id` as a strict typed field on the payload model. Session-ambient bucket scope is acceptable for resolving which repository to use, but the persisted record is the audit-trail evidence and MUST stamp the scope it was written under.
