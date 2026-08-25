---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:38838500cbd5a25c2ccde3a636175f4d4c2de6e99d6f1f3e069a57b475ce6570'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-25-tui-architecture-workspace-owner-seam-reconciliation-audit]]"
  - '[[2026-08-25-tui-architecture-s160-native-work-capture-owner-atomicity-reconciliation-audit]]'
---
# `tui-architecture` reference: `S128 Workspace projection composition`

S128 research used the accepted Workspace V1 decision, Workspace contract and S127 reference, S125-S127 implementation and audits, the owner-seam reconciliation audit, semantic discovery on Vaultspec RAG port 8766, and exact public-facade census. RAG returned the Workspace models, S126 contract family, canonical work review, and operator state projection. The RAG server reported an older incompatible release during the later reconciliation, so every semantic result was closed with whole-file reading and exact source census. No S128 Step Record currently exists.

## Summary

### Canonical dependency map

| Contributor kind | Sole public source/owner | S128 use | Current port status |
|---|---|---|---|
| `REGISTRY` | public `ValidatedRegistryAuthority.capture_law_selected_projection`, `RegistryAuthorityCapture`, and `read_current_generation` in `cadrumo.domain.calculations.registry` | capture the law-selected inspection or graded snapshot from the WORK-captured filing coordinate | S159 native capture/currentness is present; S126 registration is missing. |
| `WORK` | public visible/exact target contracts, strict frozen `ModeloWorkResolution`, the canonical selector in `cadrumo.application.modelo`, and the public active-profile pointer transaction over core pointer IO | capture work-only target resolution over one catalogue observation; for implicit bucket compose the pointer and catalogue coordinates; leave law selection to REGISTRY | Pointer-native atomic transition coordinate, atomic persistence observation, pure captured-catalogue convergence, native capture/currentness, and S126 registration are missing. |
| `BOUNDED_REVIEW` | public `build_modelo_work_review` | copy the canonical `ModeloWorkReview` unchanged into the facet; never rebuild its join | Native atomic capture and S126 registration are missing. |
| `READINESS` | `build_operator_state_projection` and its Modelo-readiness projection | copy canonical profile/registry/binding/ledger axes; never infer availability | Native atomic capture and S126 registration are missing. |
| `CLOSURE` | public application registry closure projection | copy native limbs/outcomes and refusal evidence | Native atomic capture and S126 registration are missing. |
| `CALCULATION` | canonical calculation-revision/materialization and calculation-source graph public surfaces | bounded scalar/repeated materialization plus selected canonical provenance | Native atomic capture and S126 registration are missing. |
| `LOCALE_CATALOGUE` | canonical locale resolver | requested/resolved language, exact Spanish fallback or suppression and catalogue digest | Native atomic capture and S126 registration are missing. |
| `FIELD_MANIFEST` | S127 `generate_modelo_workspace_field_manifest` | schema identity's manifest digest and explanatory schema rows only | S126 declaration exists with a stale owner identity; native capture, relocation into the sole S167 registration inventory, and corrected identity remain open. |

S128 must compose these owners only through the application-owned S126 registrations decided by the Workspace ADR. It may not import registry `_schema`, `_loader`, authoring fragments, calculation internals, repositories, adapters, CLI/MCP, Textual, journals, or persistence. S159 has promoted the registry-native surface; the remaining owner surfaces still require canonical facade promotion before registration. Workspace V1 itself is exported from `cadrumo.application.modelo` only in S129. No lazy bridge, non-`__init__` re-export module, compatibility import, or alternate projection producer is permitted.

### Two-level native-capture/S126 seam

The seam topology and consistency rules live in the accepted Workspace ADR. At current HEAD, the S159 REGISTRY native capture/current-generation pair is public and the other seven native pairs remain missing; all eight application-owned S126 registrations remain missing. S126's current epoch schema has only semantic owner plus integer generation, so its schema-version-2 opaque comparison domain and atomic no-compatibility migration remain prerequisites. S128 therefore has no legal reason to read an owner directly, and this reference does not define a second capture, generation, comparison domain, selector, or adapter contract.

### Composition sequence locator

The accepted ordering now lives only in `2026-08-24-tui-registry-api-gate-adr`: S128 invokes WORK exactly once, invokes REGISTRY from that captured filing coordinate, applies the requested-target and stored-work revision axes independently through one pure assertion operation, and only then invokes the remaining admission-specific registrations. The former instruction to resolve a target before the WORK registration is withdrawn; it would be a second work read. After those captures, S128 assembles only captured safe projections, performs the accepted same-comparison-domain second-pass currentness validation, and mints the baseline only on success.

Pagination and expansion re-present and revalidate the baseline, application process incarnation, selected revision, schema identity, contract version, sorted contributor tuple, and the schema-version-2 comparison domain of every contributor epoch. A cursor from another physical owner domain, root, or process incarnation refuses as `workspace_changed` before integer comparison; a bounded opaque cursor cannot select a new revision, requery an unpinned owner, or retain an unbounded collection. Locale-only refresh may reuse canonical identity only if the locale producer proves identical non-localized content and coordinates within the same comparison domain.

### Safe projection rules

Static inspection has schema facet plus explicit unavailable/unmeasured owner dispositions; it cannot carry materialization, provenance, or an available work-review facet. Graded projection requires bounded materialization and provenance facets and exact target/revision parity. Each capability is copied from its owner with evidence; absent measurement is `unmeasured`, not available. Source graph records retain only the existing typed `CalculationSourceRef` and approved fingerprint/reference roles. Financial values are confined to explicitly admitted bounded materialization records; they never enter baselines, refusals, diagnostics, manifest, locale metadata, cursors, or logs.

### Required implementation proof

Use real public authority fixtures, not raw mappings or mocks. The complete proof matrix, including pointer-owner transition atomicity, implicit pointer/catalogue retry and currentness, explicit pointer exclusion, comparison-domain refusal, independent revision axes, WORK ordering, and registry separation, is owned by the accepted Workspace ADR. S128 additionally retains exact `ModeloWorkReview` fixed-point parity, readiness/closure parity, generated manifest parity, baseline/cursor domain revalidation, sensitive non-retention, forbidden-import checks, and a semantic-plus-exact duplicate-authority census. Do not hardcode contributor or field counts as a successful condition; derive the producer inventory and manifest fixed point.

### Blockers

S128 is blocked on the seven remaining public native capture/current-generation surfaces, the canonical pointer-owner transition coordinate, S126 epoch schema version 2 and its no-compatibility migration, all eight application-owned registrations, process-incarnation invalidation, the S125 two-axis assertion correction, and the S167 seam-conformance fixed point. WORK is additionally blocked on the accepted atomic singleton observation, pure captured-catalogue convergence, implicit pointer/catalogue composition, and S159-backed two-axis assertion prerequisites. Public safe projections for calculation materialization/source graph and registry closure also remain insufficient. S128 owns only the capture-and-compose coordinator and no pointer mutation/counter, registry grammar, storage path, generation/domain derivation, readiness calculation, review join, closure join, source graph, locale resolver, or pre-capture work read.
