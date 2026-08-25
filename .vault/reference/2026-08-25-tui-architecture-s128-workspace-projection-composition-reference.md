---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d33d2bcd5277e44335c60db8204597c0b74c9cddf01670a1a9773451d065a425'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` reference: `S128 Workspace projection composition`

S128 research used the accepted Workspace V1 D8 decision, Workspace contract and S127 reference, S125-S127 implementation and audits, semantic discovery on Vaultspec RAG port 8766, and exact public-facade census. RAG returned the Workspace models, S126 contract family, canonical work review, and operator state projection without an index-lag warning. No S128 Step Record currently exists.

## Summary

### Canonical dependency map

| Contributor kind | Sole public source/owner | S128 use | Current port status |
|---|---|---|---|
| `REGISTRY` | `ValidatedRegistryAuthority.snapshot` and public `RegistrySnapshot` in `cadrumo.domain.calculations.registry` | law-select revision from resolved Modelo/year/period; schema identity, family dispositions, safe references and grade decision | No atomic Workspace port; owner must expose one without reopening TOML. |
| `WORK` | public `cadrumo.application.modelo` target/address contracts such as `ModeloVisibleFilingTarget`, `ModeloExactWorkUnitTarget`, and `resolve_registry_revision_for_work_target` | resolve natural/exact target, assert bucket/revision, distinguish absent/ambiguous/refused | No atomic port. |
| `BOUNDED_REVIEW` | public `build_modelo_work_review` | copy the canonical `ModeloWorkReview` unchanged into the facet; never rebuild its join | No atomic port. |
| `READINESS` | `build_operator_state_projection` / its public Modelo-readiness projection | copy canonical profile/registry/binding/ledger axes; never infer availability | No atomic port. |
| `CLOSURE` | public application registry closure projection | copy native limbs/outcomes and refusal evidence | No atomic port. |
| `CALCULATION` | canonical calculation-revision/materialization and calculation-source graph public surfaces | bounded scalar/repeated materialization plus selected canonical provenance | No atomic port. |
| `LOCALE_CATALOGUE` | canonical locale resolver | requested/resolved language, exact Spanish fallback or suppression and catalogue digest | No atomic port. |
| `FIELD_MANIFEST` | S127 `generate_modelo_workspace_field_manifest` plus its S126 producer contract | schema identityâ€™s manifest digest and explanatory schema rows only | Contract exists; no live atomic port. |

S128 must compose these owners through narrow public ports. It may not import registry `_schema`, `_loader`, authoring fragments, calculation internals, repositories, adapters, CLI/MCP, Textual, journals, or persistence. The public `cadrumo.application.modelo` facade is restored eager and must stay so: no lazy bridge, re-export module, compatibility import, alternate projection producer, or facade widening before S129.

### Mandatory owner-port shape

Each owner supplies `ModeloWorkspaceAtomicProjectionPortV1[T]` with its own frozen S126 `ModeloWorkspaceProducerContractV1`, one atomic `capture_projection_with_epoch`, and `read_current_stamp_and_epoch`. Capture returns the owner projection plus exact `ModeloWorkspaceProducerStampV1` and owner-scoped monotonic generation. S128 never mints epochs, hashes payloads as epochs, computes a substitute owner stamp, or obtains a live value while assembling. The inventory contains exactly the eight S126 contributor kinds; generated S127 manifest is the `FIELD_MANIFEST` contribution.

All eight live ports are currently missing. This is the principal implementation blocker: S128 cannot honestly assemble a success until each canonical owner exposes its port and generation source. Adding them requires owner-local work with atomic storage/read semantics; a Workspace-side adapter that reads arbitrary repositories would violate D8 and create a duplicate assembly authority.

### Admission and two-pass algorithm

1. Parse only the strict V1 request header. Unknown version returns the minimal version refusal before target/secure resolution.
2. Resolve visible or exact target through the canonical public addressing owner. Missing, ambiguous, bucket assertion, or revision assertion failures produce typed domain refusals; stored revision is assertion only, never a selector.
3. For `static_inspection`, obtain only the registry/manifest/locale coordinates necessary for schema inspection. Do not capture or expose work review, materialization, or provenance. For `graded_snapshot`, request the law-selected grade; an insufficient grade refuses without downgrade.
4. Capture every contributor port in deterministic `(owner, producer)` identity order. Validate each capture against its declared S126 contract before any join.
5. Assemble only captured safe projections. Copy `ModeloWorkReview`, readiness, closure limbs, materialization/provenance and locale data from their owners. Apply bounded schema/materialization/provenance facets, stable cursors, canonical section/row identities, and capability dispositions; do not execute formula/selector grammar.
6. Re-read every portâ€™s current stamp and epoch in the same order. Require exact equality to the captured coordinates. Unknown/changed coordinates cause a bounded whole-read retry; exhaustion returns `workspace_changed` or `consistency_unavailable`. Never retain a partial facet across retries.
7. Only after pass two succeeds, mint the opaque baseline from sorted contributor tuples/stamps, selected target/revision, Workspace V1 contract, registry schema identity/fingerprint, locale catalogue digest, field-manifest digest, and safe request coordinate. No raw value, secret, source identity, repository key, or authorization enters the token.

Pagination and expansion re-present the baseline, selected revision, schema identity, contract version and sorted contributor tuple. A cursor is bounded and opaque; it cannot select a new revision, requery an unpinned owner, or retain an unbounded collection. Locale-only refresh may reuse canonical identity only if the locale producer proves identical non-localized content and coordinates.

### Safe projection rules

Static inspection has schema facet plus explicit unavailable/unmeasured owner dispositions; it cannot carry materialization, provenance, or an available work-review facet. Graded projection requires bounded materialization and provenance facets and exact target/revision parity. Each capability is copied from its owner with evidence; absent measurement is `unmeasured`, not available. Source graph records retain only the existing typed `CalculationSourceRef` and approved fingerprint/reference roles. Financial values are confined to explicitly admitted bounded materialization records; they never enter baselines, refusals, diagnostics, manifest, locale metadata, cursors, or logs.

### Required implementation proof

Use real public authority fixtures, not raw mappings or mocks. Prove target ambiguity/absence and revision assertion; static versus grade separation; every ownerâ€™s capture/stamp/epoch mismatch; A-to-B-to-A invalidation; torn-read retry/refusal; exact `ModeloWorkReview` fixed-point parity; readiness/closure parity; generated manifest parity; cursor revalidation; sensitive non-retention; no forbidden imports; and a semantic-plus-exact duplicate-authority census. Do not hardcode contributor or field counts as a successful condition; derive the producer inventory and manifest fixed point.

### Blockers

S128 is blocked on public atomic stamped ports and monotonic generation sources for registry, work, bounded review, calculation, readiness, closure, and locale catalogue, plus the live `FIELD_MANIFEST` port wrapper. It is also blocked on public safe projection functions for the calculation-source graph/materialization and registry closure if their existing surfaces are not sufficient. These must be introduced at their current owners, atomically with consumers, without aliases or bridges. S128 itself owns only the one capture-and-compose coordinator and no new registry grammar, storage path, readiness calculation, review join, or locale resolver.
