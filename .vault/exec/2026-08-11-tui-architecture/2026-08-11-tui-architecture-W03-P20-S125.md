---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:c9f87ac965c16eb022b6b529e010813e79e8c6122bf1a86c7f5962cdd850b579'
step_id: 'S125'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define strict Workspace V1 version headers, visible and exact target admission, inspection and graded result arms, projection, bounded facets, schema and provenance records, capability and refusal families, locale summary, and safe read baseline without mutation authority

## Scope

- `src/cadrumo/application/modelo/_workspace_models.py`
- `src/cadrumo/application/modelo/tests/test_workspace_models.py`

## Description

- Grounded the Workspace V1 boundary with Vaultspec RAG and exact source census before correcting provenance.
- Retained the approved tagged canonical target arms, strict readiness projection, bounded nested collections/cursors, and discriminated materialization records.
- Replaced the lossy parallel workspace provenance DTO with a direct `CalculationSourceRef` field. The canonical source ref retains resolver, resolved binding source, arbitrary contributor-source kind, optional contributor binding source, lineage role, ordinary transaction source/parent references, optional fingerprint, and dependency treatment without a second validator or narrowed identifier aliases.
- Added integration contract coverage that round-trips primary and contributor canonical transaction provenance with external contributor taxonomy, non-digest fingerprints, and both dependency-treatment values.

## Outcome

Closed. Independent review approved the final provenance correction. The plan checkbox was closed through Vaultspec after approval; no compatibility shim, alternate provenance vocabulary, facade re-export, or second provenance owner was added.

## Evidence

- Vaultspec RAG located `CalculationSourceRef` at `domain.modelos._calculation_revision` and its sanctioned `domain.modelos` facade export. Exact source census confirmed the Workspace record is only a subject plus that canonical type; no parallel lineage fields remain.
- Scoped Ruff and ty passed.
- Focused integration suite passed: 17 tests.
- Diff check passed.
- Independent S125 review approved the final correction before closure.
