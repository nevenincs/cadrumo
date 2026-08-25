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
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-25-tui-architecture-workspace-owner-seam-reconciliation-audit]]"
---
# `tui-architecture` reference: `S128 Workspace projection composition`

S128 research used the accepted Workspace V1 decision, Workspace contract and S127 reference, S125-S127 implementation and audits, the owner-seam reconciliation audit, semantic discovery on Vaultspec RAG port 8766, and exact public-facade census. RAG returned the Workspace models, S126 contract family, canonical work review, and operator state projection. The RAG server reported an older incompatible release during the later reconciliation, so every semantic result was closed with whole-file reading and exact source census. No S128 Step Record currently exists.

## Summary

### Canonical dependency map

| Contributor kind | Sole public source/owner | S128 use | Current port status |
|---|---|---|---|
| `REGISTRY` | `ValidatedRegistryAuthority.snapshot` and public `RegistrySnapshot` in `cadrumo.domain.calculations.registry` | law-select revision from resolved Modelo/year/period; schema identity, family dispositions, safe references and grade decision | Native atomic capture and S126 registration are missing. |
| `WORK` | public target/address contracts and `resolve_registry_revision_for_work_target` | resolve natural/exact target, assert bucket/revision, distinguish absent/ambiguous/refused | Native atomic capture and S126 registration are missing. |
| `BOUNDED_REVIEW` | public `build_modelo_work_review` | copy the canonical `ModeloWorkReview` unchanged into the facet; never rebuild its join | Native atomic capture and S126 registration are missing. |
| `READINESS` | `build_operator_state_projection` and its Modelo-readiness projection | copy canonical profile/registry/binding/ledger axes; never infer availability | Native atomic capture and S126 registration are missing. |
| `CLOSURE` | public application registry closure projection | copy native limbs/outcomes and refusal evidence | Native atomic capture and S126 registration are missing. |
| `CALCULATION` | canonical calculation-revision/materialization and calculation-source graph public surfaces | bounded scalar/repeated materialization plus selected canonical provenance | Native atomic capture and S126 registration are missing. |
| `LOCALE_CATALOGUE` | canonical locale resolver | requested/resolved language, exact Spanish fallback or suppression and catalogue digest | Native atomic capture and S126 registration are missing. |
| `FIELD_MANIFEST` | S127 `generate_modelo_workspace_field_manifest` | schema identity's manifest digest and explanatory schema rows only | S126 declaration exists with a stale owner identity; native capture, relocation into the sole S167 registration inventory, and corrected identity remain open. |

S128 must compose these owners only through the application-owned S126 registrations decided by the Workspace ADR. It may not import registry `_schema`, `_loader`, authoring fragments, calculation internals, repositories, adapters, CLI/MCP, Textual, journals, or persistence. Native owner surfaces are promoted through their canonical package facades during S159-S166; Workspace V1 itself is exported from `cadrumo.application.modelo` only in S129. No lazy bridge, non-`__init__` re-export module, compatibility import, or alternate projection producer is permitted.

### Two-level native-capture/S126 seam

Per the amended Workspace ADR, each canonical owner supplies a native atomic projection-plus-generation capture and current-generation read. `cadrumo.application.modelo` alone supplies exactly one stateless S126 realization for each of the eight fixed contributor identities. A realization calls its native capture exactly once, projects only the captured immutable value, derives the stamp from its S126 contract, and carries the native generation unchanged. It owns no state, counter, cache, selector, join, or second owner read. S128 invokes those registrations and never mints generations, hashes payloads as epochs, or computes substitute owner stamps.

All eight native captures and all eight S126 registrations are currently missing. This is the principal implementation blocker. A stateless S126 realization is application composition, not an adapter authority; any realization that reads a repository or loader, recomputes owner semantics, derives its own generation, or retains a cache would instead be a forbidden duplicate authority.

### Admission and two-pass algorithm

1. Parse only the strict V1 request header. Unknown version returns the minimal version refusal before target/secure resolution.
2. Resolve visible or exact target through the canonical public addressing owner. Missing, ambiguous, bucket assertion, or revision assertion failures produce typed domain refusals; stored revision is assertion only, never a selector.
3. For `static_inspection`, capture exactly registry, work, locale-catalogue, and field-manifest registrations. Do not capture or expose bounded review, calculation, readiness, closure, materialization, or provenance. For `graded_snapshot`, capture all eight registrations and request the law-selected grade; an insufficient grade refuses without downgrade.
4. Invoke the selected S126 registrations in deterministic `(owner, producer)` identity order. Each registration performs exactly one native capture. Validate each result against its declared S126 contract before any join.
5. Assemble only captured safe projections. Copy `ModeloWorkReview`, readiness, closure limbs, materialization/provenance and locale data from their owners. Apply bounded schema/materialization/provenance facets, stable cursors, canonical section/row identities, and capability dispositions; do not execute formula/selector grammar.
6. Ask every selected registration for its current contract-derived stamp and owner-native generation in the same order. Require exact equality to the captured coordinates. Unknown, changed, or cross-process-incarnation coordinates cause a bounded whole-read retry or refusal; exhaustion returns `workspace_changed` or `consistency_unavailable`. Never retain a partial facet across retries.
7. Only after pass two succeeds, mint the opaque baseline from sorted contributor tuples/stamps, selected target/revision, Workspace V1 contract, registry schema identity/fingerprint, locale catalogue digest, field-manifest digest, and safe request coordinate. No raw value, secret, source identity, repository key, or authorization enters the token.

Pagination and expansion re-present the baseline, selected revision, schema identity, contract version and sorted contributor tuple. A cursor is bounded and opaque; it cannot select a new revision, requery an unpinned owner, or retain an unbounded collection. Locale-only refresh may reuse canonical identity only if the locale producer proves identical non-localized content and coordinates.

### Safe projection rules

Static inspection has schema facet plus explicit unavailable/unmeasured owner dispositions; it cannot carry materialization, provenance, or an available work-review facet. Graded projection requires bounded materialization and provenance facets and exact target/revision parity. Each capability is copied from its owner with evidence; absent measurement is `unmeasured`, not available. Source graph records retain only the existing typed `CalculationSourceRef` and approved fingerprint/reference roles. Financial values are confined to explicitly admitted bounded materialization records; they never enter baselines, refusals, diagnostics, manifest, locale metadata, cursors, or logs.

### Required implementation proof

Use real public authority fixtures, not raw mappings or mocks. Prove target ambiguity/absence and revision assertion; static versus grade separation; every ownerâ€™s capture/stamp/epoch mismatch; A-to-B-to-A invalidation; torn-read retry/refusal; exact `ModeloWorkReview` fixed-point parity; readiness/closure parity; generated manifest parity; cursor revalidation; sensitive non-retention; no forbidden imports; and a semantic-plus-exact duplicate-authority census. Do not hardcode contributor or field counts as a successful condition; derive the producer inventory and manifest fixed point.

### Blockers

S128 is blocked on the eight public native atomic capture/current-generation surfaces, their exact application-owned S126 registration inventory, process-incarnation invalidation, and the S167 seam-conformance fixed point. It is also blocked on public safe projections for calculation materialization/source graph and registry closure where the current public surfaces are insufficient. S159-S166 must introduce native surfaces at their canonical owners with atomic facade promotion; S167 must register them without state or semantic recomputation. S128 owns only the capture-and-compose coordinator and no registry grammar, storage path, generation, readiness calculation, review join, closure join, source graph, or locale resolver.
