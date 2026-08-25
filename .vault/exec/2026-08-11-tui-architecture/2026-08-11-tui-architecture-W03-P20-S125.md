---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:9c6599c4261ee9d43c64b244f077d0da6d0d7781690336d1dd1ad468990a26e3'
step_id: 'S125'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define strict Workspace V1 version headers, visible and exact target admission, inspection and graded result arms, projection, bounded facets, schema and provenance records, capability and refusal families, locale summary, and safe read baseline without mutation authority

## Scope

- `src/cadrumo/application/modelo/_workspace_models.py`

## Description

- Grounded the Workspace V1 boundary in the accepted registry API ADR, Workspace V1 contract reference, S125 audit, semantic RAG, and exact source census.
- Kept canonical `ModeloVisibleFilingTarget` and `ModeloExactWorkUnitTarget` as the operands of narrow literal-tagged Workspace arms. The public request and domain refusal now carry the tagged arms; they do not shape-sniff, reparse, or reconstruct a parallel target grammar.
- Bound every capability to its exact resolved target and explicit selected revision. Baselines and all bounded facets carry and validate the V1 version, selected revision, schema identity and fingerprint, baseline, and sorted contributor tuple.
- Added typed schema destinations for continuity, applicability, constraints, formula operands, relation endpoints, and export exposure, with executable finite bounds for eager nested collections.
- Replaced nullable materialization payloads with strict scalar and repeated-row discriminated record arms.
- Kept provenance as a bounded redacted Workspace DTO: canonical resolver/source kinds and lineage role, safe reference, optional fingerprint, and parent reference are preserved without raw `CalculationSourceRef` or source-object identity.
- Added a strict typed Workspace readiness projection that preserves the canonical profile, registry, binding, ledger-preflight, nullable ledger verdict, issue, and aggregate-ready axes without collapsing them into generic facts or inferring capability availability.
- Bounded localized values, cursors, facts, evidence references, facet records, contributors, schema relationships, repeated rows, provenance rows, readiness rows, family dispositions, and closure limbs.
- Added integration-marked adversarial tests for tagged target parsing, safe provenance, typed schema relationship destinations, real materialization discrimination, collection and cursor limits, exact capability-revision binding, and projection coordinate drift.

## Outcome

Corrected implementation is review-ready. S125 remains open pending independent re-review; no plan checkbox or status was closed. The public application facade and executable workspace service remain separately owned, and this step adds no compatibility shim, fallback parser, duplicate owner, or facade re-export.

## Notes

Vaultspec RAG confirmed the governing Workspace decision and canonical model family before the correction. The final code-index query was temporarily unavailable while the shared index refreshed; exact `rg` census is the closing redeclaration evidence: every `ModeloWorkspace*` definition is in the one canonical model module, no production compatibility bridge exists, and the removed `_target_from_mapping`, `_adapt_wire_target`, raw `CalculationSourceRef`, and raw `ProjectionModeloReadiness` references have zero matches there.

Focused evidence: `uv run --no-sync ruff check src/cadrumo/application/modelo/_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_models.py` passed; `uv run --no-sync basedpyright src/cadrumo/application/modelo/_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_models.py` passed with 0 errors; `uv run --no-sync pytest -q -o addopts='' -m integration src/cadrumo/application/modelo/tests/test_workspace_models.py` passed with 16 tests; `git diff --check` passed for the owned paths.
