---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:8acd8bd4b3d38339dc738d84b551fc43d0427d5efd1254965c467bba0dbe5bc8'
related:
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - '[[2026-08-25-tui-architecture-s160-approved-amendment-architecture-review-audit]]'
---

# `tui-architecture` reference: `Workspace V1 contract blueprint`

## Summary

This reference grounds the strict frontend-neutral Modelo Workspace V1 model
boundary required by `W03.P20.S125`. The audit led with semantic code and ADR
search through `vaultspec-rag` on port 8766, then confirmed exact symbols with
`rg`, full-file reads, and an exact `git grep` against commit
`eeb54d2e336a4b2eb19a138f9d66da5d12088c0b`.

At that audited HEAD there is no tracked `_workspace_models.py`, no public `ModeloWorkspaceRequest`, `ModeloWorkspaceResult`, `ModeloWorkspaceProjection`, or `ModeloWorkspaceBaseline`, and no competing Workspace version field. An untracked peer-owned `_workspace_models.py` appeared after the audit began; it is candidate implementation work, not pre-existing authority, and was not read, edited, or staged for this reference.

S125 is therefore a real model-boundary gap. It should define the strict V1
types only. Target resolution, registry admission, review assembly, readiness,
closure, calculation materialization, source lineage, localization, epochs,
facade export, and conformance remain owned by their existing producers or by
later steps. The model file must carry no repository, callback, Textual, CLI,
MCP, persistence, operation-submission, edit, or mutation authority.

## Contract blueprint

### Version dispatch and result arms

Dispatch reads only that header. A missing, old, unknown, or future version returns a minimal version-only refusal before target parsing or secure-state access. Do not introduce a generic shared `version` field or reuse an operation endpoint version: the accepted operation contract explicitly keeps every endpoint axis separate.

The ADR-mandated public family is `ModeloWorkspaceRequest`,
`ModeloWorkspaceResult`, `ModeloWorkspaceProjection`,
`ModeloWorkspaceRefusal`, and `ModeloWorkspaceBaseline`, with V1-specific
implementation arms where needed. Every coordinate-bearing V1 success or
domain refusal echoes `contract_version = 1`; the pre-parse version refusal
echoes the requested and sole supported versions without claiming the rejected
payload is V1. Result discrimination must keep three claims visibly separate:

- static inspection success, which carries no admitted snapshot or
  materialized work values;
- exact graded-snapshot success, which records requested, declared, and
  effective grade without downgrade; and
- typed refusal, which cannot smuggle a partial snapshot into a success arm.

Closed axes are typed enums or literals, not strings hidden in an untyped mapping.

### Target admission

The visible operand contains Modelo, filing year, `Period`, an assertion-only registry revision, and optional bucket. The exact operand contains `WorkUnitId` and an optional bucket assertion. Do not redeclare these coordinates or admit a calculation revision selector into the Workspace request.

Their behavior already distinguishes explicit-id absence, natural absence, contradiction, revision conflict, and multiple natural matches.

There is one constraint-shape gap to handle deliberately: the two public
target operands are frozen dataclasses, not strict Pydantic models carrying an
explicit discriminator. Do not shadow them with same-named Workspace models.
If the serialized V1 boundary needs an explicit discriminator, use a narrow
Workspace-owned tagged arm that contains the canonical operand, or reconcile
the canonical target contract first; never create a second natural-addressing
authority. Zero natural matches must remain an explicit absent-work read state,
and no S125 model may imply creation.

### Revision assertion contract-correction locator

The assertion decision and all outcome semantics live only in
`2026-08-24-tui-registry-api-gate-adr`. The current S125 implementation has one
`ModeloWorkspaceRevisionAssertionV1` attached as `revision_assertion`; it can
name only the requested visible-target revision and cannot retain the stored
work revision independently. The corrected strict Workspace V1 shape replaces
that field atomically with fixed `requested_revision_assertion` and
`stored_revision_assertion` records. Each has a source-fixed discriminator,
optional asserted `RevisionId`, and the closed disposition set `not_present`,
`matched`, or `mismatched`, with validators that bind presence to disposition.
The resolved target and typed revision-mismatch refusal carry both records, so
natural absence, exact lookup, visible persisted work, and either or both
mismatch sources remain distinguishable. S128 populates neither axis from
generic facts and evaluates both only after the S159 law-selected capture. The
old field and its reader are removed; there is no alias, default synthesis,
compatibility arm, or second assertion model.

### Registry admission and schema projection

A missing declaration is distinct from an explicit applicability declaration even though `effective_authority_grade` reads both at the fail-closed floor.

Neither may cross Workspace V1 directly. S125 needs application DTOs that preserve canonical IDs and declared facts while excluding source paths, compiler objects, selectors, and snapshot capability.

Preserve the existing namespaces rather than minting strings: `CasillaId`; `ModeloId`, `RevisionId`, `BindingId`, `FormulaId`, `RelationId`, `ParameterId`, `LegalRefId`, and `SourceRefId`; formula operand and relation endpoint discriminators; `BindingSourceKind`; and typed aggregation and applicability axes. Scalar values remain keyed by `CasillaId`. Never flatten a repeated row into a synthetic casilla id.

The authority currently consumes that identity for caching but does not expose an atomic public schema-identity projection. S125 declares the safe identity DTO; S126 defines only the application-owned stamped envelope and structural port protocol; S159 adds the registry-native capture and generation; S167 owns its sole S126 registration; and S128 invokes and composes that registration. None may fabricate an owner generation from a local payload hash.

### Canonical bounded review



Workspace V1 must carry that exact object or a typed ineligible-facet
disposition. It must not widen `ModeloWorkReview`, reconstruct its casillas,
repeat its join, or reuse the compact CLI `WorkReviewPayload`, which deliberately
drops values and detailed provenance. Static inspection cannot carry this
facet. Absent work cannot be passed through the existing producer because that
producer requires a persisted work unit; absence therefore needs an explicit
Workspace disposition rather than a dummy review.

Every collection lacking an authoritative finite bound needs a typed page or
expansion envelope. Such a facet must echo contract version, selected revision,
registry schema identity and fingerprint, baseline, and the same contributor
tuple used by the root projection. Do not define unpinned pagination or an
eager `tuple` merely because current fixtures are small.

### Readiness, closure, calculation, and provenance owners

The canonical operator readiness record is `ProjectionModeloReadiness` at
`src/cadrumo/application/state_projection.py:587`, produced only as part of
`build_operator_state_projection` at
`src/cadrumo/application/state_projection.py:994`. Preserve its exact axes:
`profile_ready`, `per_operation_requirements_assessed`, profile refusal and
missing requirements, `registry_ready`, `binding_ready`, missing bindings,
`ledger_preflight_required`, nullable `ledger_ready`, ledger issues, and
aggregate `ready`. The producer's aggregate does not prove the per-operation
axis was assessed, so neither `ready` nor the assessment flag can independently
yield Workspace capability `available`. A separate stamped owner verdict is
required; until it exists, report `unmeasured`.

Reuse these owner facts and their evidence/disposition semantics.

The cross-authority `RegistryClosureReport` join remains development-only at
`dev/registry/conformance/closure.py:179`. Production Workspace code must not
import it or recreate it. Until a canonical production join/port exists,
Workspace closure capability is `unmeasured`; the individual public limbs may
still be projected honestly without claiming the missing conjunction.



Workspace provenance may select and redact this graph, but it cannot invent a
second resolver, edge, identity, or causal ordering. Preserve resolver identity,
resolved binding source, contributor kind and typed binding source when
applicable, `PRIMARY`/`CONTRIBUTOR` role, safe reference, optional fingerprint,
and parent reference. Do not expose `RowSourceIdentity.source_row_identity`,
ledger transaction bodies, profile facts, or secret/source-bearing exception
text. Legal and source grounding remains on canonical observations and schema
records; do not duplicate it onto a lineage row whose owner does not carry it.

### Capability, refusal, locale, and baseline

S125 needs a Workspace-owned closed capability subject set for schema inspection, calculation materialization, verification readiness, filing-draft readiness, and filing-export readiness. Its disposition set is exactly `available`, `not_applicable`, `refused`, or `unmeasured`. This is not CLI `TuiCapability`, not `ServiceCapability`, and not registry closure outcome renamed. Each row binds the exact target and revision, canonical producer, safe evidence, and source disposition.

A domain refusal needs a stable code, affected capability or admission
boundary, requested coordinate, selected coordinate when known, bounded safe
facts, canonical evidence references, owner/disposition, reconsideration
condition, and optional `ActionReference`. It must not contain localized prose,
raw exceptions, repositories, commands, financial values, or raw source
identity. The pre-parse version refusal is a separate smaller arm.

Locale uses the closed `OutputLanguage` enum at `src/cadrumo/core/external_constants.py:511`. It currently returns only the rendered scalar, not key, resolved language, or fallback/suppression disposition. S125 can define the safe locale summary and per-field resolution DTO, but S165 must expose those facts through the canonical native locale capture, S167 must register that surface once under S126, and S128 must invoke it rather than infer resolution from string equality. Locale never changes IDs, values, provenance, capability, revision, or baseline.

`ModeloWorkspaceBaseline` is a new opaque safe-read consistency token. The model must state only consistency identity. S126 owns the application envelope; S159-S166 own native generations; S167 owns their sole registrations; and S128 owns retry, process-incarnation invalidation, and token minting. The baseline is never accepted as an edit baseline, command credential, approval, mutation precondition, persistence key, or operation refresh authority.

S126 epoch schema version 2 adds one opaque safe comparison-domain token copied
unchanged from each native owner's physical-scope/process-incarnation domain.
The epoch tuple and its digest include that token. `ModeloWorkspaceBaselineV1`
adds a `contributor_epoch_digest` over the sorted complete epoch coordinates,
separate from its static `contributor_stamp_digest`; its token and every cursor
or facet continuation bind that epoch digest.
Raw root, bucket, namespace, key and pointer coordinates remain outside S125
models. Cross-domain currentness refuses before integer comparison, and no
epoch-schema-version-1 compatibility reader remains. This reference owns only
the safe Workspace token placement; domain derivation and comparison semantics
remain in the accepted ADR, while lower owners return no Workspace type.

## Forbidden dependency edges

- No import from `cadrumo.entrypoints`, `cadrumo.adapters`, concrete
  persistence, repository implementations, operation journals, CLI payloads,
  Textual, MCP, or `dev`.
- No private registry module import from `application.modelo`; consume the
  public `cadrumo.domain.calculations.registry` facade. Do not export
  `RegistrySnapshot`, `RegistryRevisionInspection`, `ModeloRevision`, schema
  definitions, selectors, paths, or raw catalogue objects in Workspace DTOs.
- No application write service, `ModeloEditContractV1`, operation submission,
  callback, callable, executor, verification/file/export mutation, work-unit
  creation, or refresh-target effect authority in S125.
- No new address selector, law-revision selector, review assembler, readiness
  calculation, closure join, calculation graph, locale-key constructor, action
  catalogue, source taxonomy, or compatibility shim.
- No untyped `dict[str, Any]`, free-form facts bag, raw exception, localized
  command prose, financial value in refusal/baseline metadata, or unsafe source
  identity. Bounded typed fact variants are required.

## Current implementation state after the reconciled census

- S125 supplies the sole strict Workspace V1 request, admission, result,
  projection, refusal, baseline, bounded-facet, capability, materialization,
  provenance, readiness, and schema DTO family in `_workspace_models.py`.
- S126 supplies the sole application-owned producer contract, stamp, epoch,
  structural port, and fixed eight-kind inventory family in
  `_workspace_producers.py`; its current epoch schema lacks the approved opaque
  comparison domain and requires the atomic schema-version-2 correction. It
  intentionally supplies no live owner surface.
- S125's current single requested-revision assertion cannot preserve the
  independent stored-work axis and requires the atomic two-axis correction
  located above before S128 composition.
- S127 supplies the sole generated field-classification denominator in
  `_workspace_manifest.py`. Its early field-manifest contract owner identity is
  scheduled for correction and atomic relocation into S167's registration
  inventory; no second manifest walker is permitted.
- All eight canonical native atomic capture/current-generation surfaces remain
  missing, as do their eight application-owned S126 registrations.
- `ModeloWorkReview` is complete and public; its native capture and complete
  Workspace fixed-point embedding remain open.
- Registry tree identity exists, but its public native atomic inspection or
  snapshot capture and process-incarnation-local generation remain open.
- Readiness exists, but native capture and separately stamped per-capability
  verdicts remain open; aggregate readiness must not be promoted.
- Closure limbs exist, but the only full cross-authority join remains under
  `dev`; production closure stays `unmeasured` until its canonical owner lands.
- Calculation/source lineage exists, but its bounded redacted native projection
  and Workspace facet delivery remain open.
- Localization resolves values, but its native requested/resolved locale and
  fallback/suppression projection remains open.
- Workspace assembly, process-incarnation validation, facade export, complete
  conformance, and dependency receipt remain open. Semantic and exact censuses
  found no concrete Workspace assembler, compatibility reader, shim, alias,
  fallback, re-export bridge, or parallel Workspace V1 authority.

These gaps are intentionally split across the plan: S125 declares the safe
models; S126 owns the application stamped-envelope and structural port types;
S127 owns the generated field denominator; S159-S166 own native atomic captures
and generations; S167 owns the exact S126 registration fixed point; S128 owns
assembly from those registrations; S129 owns facade export; and S130 proves
conformance and duplicate-authority absence. Pulling later-step behavior into
`_workspace_models.py` or lower-layer owners would create the redeclaration or
dependency inversion this blueprint is meant to prevent.
