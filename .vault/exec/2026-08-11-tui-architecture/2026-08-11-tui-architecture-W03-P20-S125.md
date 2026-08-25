---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:0e7198cfe5999f77193943d798bdbf24f630c3dd595950dce71a901222d1e053'
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
- Replaced the lossy parallel workspace provenance DTO with a direct `CalculationSourceRef` field. The canonical source ref now retains resolver, resolved binding source, arbitrary contributor-source kind, optional contributor binding source, lineage role, ordinary transaction source/parent references, optional fingerprint, and dependency treatment without a second validator or narrowed identifier aliases.
- Added integration contract coverage that round-trips primary and contributor canonical transaction provenance with external contributor taxonomy, non-digest fingerprints, and both dependency-treatment values.

## Outcome

Corrective implementation is review-ready. S125 remains open pending independent re-review; no plan checkbox or status was closed. This correction adds no compatibility shim, alternate provenance vocabulary, facade re-export, or second provenance owner.

## Notes

RAG located `CalculationSourceRef` at `domain.modelos._calculation_revision` and its sanctioned `domain.modelos` facade export. Exact source census confirmed the application workspace record is now only a subject plus that canonical type; no parallel lineage fields remain.

Focused evidence: `uv run ruff check src/cadrumo/application/modelo/_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_models.py` passed; `uv run pytest src/cadrumo/application/modelo/tests/test_workspace_models.py -m integration -q` passed with 17 tests; `uv run ty check src/cadrumo/application/modelo/_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_models.py` passed; `git diff --check` passed.
