---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:92dee64c0548374b806f77e3025fc64df8efb5f8aad467f808cc59eb9893cc56'
related:
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-25-tui-architecture-workspace-v1-contract-reference]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `S125 Workspace V1 model review`

## Scope

Independent architecture-grade review of S125 commit `6f210459d3` against the accepted Workspace V1 ADRs, the implementation plan, and the grounded contract reference. The review included line-by-line model inspection, semantic and exact definition census, focused integration tests, Ruff, and basedpyright. No source correction was made during review.

## Findings

### workspace-coordinate-binding | high | Capability and facet records are not pinned to their exact Workspace coordinate

`ModeloWorkspaceCapabilityV1` omits the exact target and law-selected revision required for every copied capability answer. `ModeloWorkspaceBoundedFacetV1` likewise omits the contract version, selected revision, schema identity, baseline token, and contributor-stamp coordinate required to make independently traversed pages consistency-verifiable. A consumer therefore cannot prove that a capability or later facet page belongs to the projection it is rendering.

### schema-denominator-shape | high | Schema records cannot represent the accepted explanatory identity universe

`ModeloWorkspaceSchemaRecordV1` carries a primary reference, label, classification, family disposition, and legal/source references, but has no typed destinations for continuity, applicability, constraints, formula operands, relation endpoints, export exposure, or the remaining accepted explanatory identity relationships. S127 cannot generate the ADR-mandated exhaustive manifest into this destination without omission or an untyped escape hatch.

### materialization-discrimination | high | Materialization uses a nullable arm container instead of a discriminated union

`ModeloWorkspaceMaterializationRecordV1` exposes a free `kind` plus two nullable payload fields and repairs the state with a model validator. The accepted boundary requires strict discriminated records. Separate scalar and repeated-row record arms with literal discriminators are required so the schema itself is closed and consumers do not inherit nullable-arm interpretation.

### boundary-boundedness | medium | Display values and cursors are unbounded

`ModeloWorkspaceLocalizedTextV1.value` and `ModeloWorkspaceBoundedFacetV1.next_cursor` accept unrestricted strings. This violates the bounded DTO and traversal posture and permits an otherwise bounded page to carry unbounded presentation or cursor data.

### static-analysis | medium | Focused basedpyright reports nine errors

The three identifier `TypeAdapter` instances infer `Unknown`, their validated values flow into typed constructors as unknown arguments, mapping adaptation retains unknown key/value types, and `ModeloWorkspaceDomainRefusalV1` reaches across class privacy to `_adapt_wire_target`. The implementation does not meet the project static-analysis gate.

### duplicate-owner-census | low | No redeclaration, shim, alias, or re-export bridge was found

Vaultspec RAG and exact source census found all `ModeloWorkspace*` definitions in the S125 canonical model module and no production imports or compatibility surfaces. This clean result must be retained by the correction and later public-boundary work; it does not offset the blocking contract findings above.

### target-wire-redeclaration | high | Shape sniffing creates a second target grammar instead of tagged canonical arms

`_target_from_mapping` and `ModeloWorkspaceRequestV1._adapt_wire_target` at `src/cadrumo/application/modelo/_workspace_models.py:157` redeclare allowed-key sets, select an arm by the presence of `work_unit_id`, reparse `Period`, and reconstruct the canonical target dataclasses. The request target at line 213 is therefore not a public discriminated union, and the refusal at line 668 reuses the private validator across class ownership. This is distinct from the clean duplicate-model census: it is a parallel wire-parser authority over existing target models. Replace it with narrow Workspace-owned literal-tagged arms containing the canonical operands, or first reconcile the canonical target contract; delete the shape-sniffing helper without an alias or bridge.

### readiness-contract-loss | high | Generic facts cannot preserve the canonical readiness axes

The model family has no typed Workspace readiness projection, while `ModeloWorkspaceCapabilityV1` at `src/cadrumo/application/modelo/_workspace_models.py:429` offers only an open-ended tuple of name/value facts. That shape cannot preserve `profile_ready`, `per_operation_requirements_assessed`, profile refusal and missing requirements, registry and binding readiness, ledger preflight and nullable ledger readiness, issues, and aggregate readiness exactly as the accepted ADR requires. S128 would have to encode a parallel fact-name convention or drop owner data. Add a strict typed projection of the canonical readiness record and keep evidence facts explanatory only.

### nested-payload-bounds | medium | The outer page limit leaves nested record cardinality unbounded

Beyond the unrestricted localized value at `src/cadrumo/application/modelo/_workspace_models.py:286` and cursor at line 470, the page-size check at lines 473-483 bounds only outer records. `section_path`, legal/source references, repeated-row values and provenance, family dispositions, and evidence-horizon references have neither authoritative finite maxima nor bounded expansion contracts. Declare executable bounds for each nested collection or move it behind a coordinate-pinned page or expansion envelope; add oversize refusal tests.

## Recommendations

Keep S125 open. Amend the canonical model module in place to bind capability and facet rows to exact coordinates, provide typed schema relationship destinations, replace the materialization container with a real discriminated union, bound all strings and cursors, and clear focused basedpyright without aliases, shims, re-export bridges, or duplicate owners. Extend adversarial tests for every repaired invariant, then repeat this independent review before S125 closure.
