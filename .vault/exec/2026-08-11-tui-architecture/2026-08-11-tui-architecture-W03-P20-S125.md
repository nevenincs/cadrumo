---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:908557606f044a0db5047931c1fdc7568f265750fd1c1801eb0461528c38045f'
step_id: 'S125'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define strict Workspace V1 version headers, visible and exact target admission, inspection and graded result arms, projection, bounded facets, schema and provenance records, capability and refusal families, locale summary, and safe read baseline without mutation authority

## Scope

- `src/cadrumo/application/modelo/_workspace_models.py`

## Description

- Grounded the Workspace V1 boundary in the approved plan, workspace and registry ADRs, audit corpus, and semantic code census before declaring its model family.
- Reused canonical `ModeloVisibleFilingTarget`, `ModeloExactWorkUnitTarget`, `ModeloWorkReview`, core identity and authority values, registry identifiers, filing scalar, locale, lineage, and operator-action reference rather than redeclaring equivalent concepts.
- Defined strict frozen V1 request, admission, projection, bounded facet, schema, provenance, capability, refusal, locale, and baseline records in the owning `application.modelo` module.
- Separated static inspection from graded snapshots, prohibited static materialization and review disclosure, and required the closed producer-declared capability denominator on successful projections.
- Added focused contract tests for canonical target wire adaptation, strict/frozen request behavior, discriminated version refusal handling, and unavailable bounded facets.
- Ran focused static and integration gates and checked whitespace errors for owned paths.

## Outcome

Implementation is review-ready. The S125 checkbox remains open pending independent review. The public application facade and executable workspace service are deferred to their separately owned plan steps; this step adds neither a shim nor a cross-owner private import.

## Notes

Semantic RAG returned an incomplete code index warning for absent-result searches, so exact source census was used alongside positive semantic findings. The adjudicated existing owners were `ModeloWorkReview` for the review facet, `_work_addressing` for request targets, core for identity/authority/locale/provenance primitives, `domain.calculations.registry` for registry identifiers, `domain.filing` for materialized scalar values, and `application.operator_actions` for recovery references. No duplicate Workspace V1 model family was found in production `application.modelo` sources.

Focused evidence: `uv run ruff check` passed; `uv run ty check` passed; `uv run pytest -q -o addopts='' -m integration src/cadrumo/application/modelo/tests/test_workspace_models.py` passed with 3 tests; `git diff --check` passed for owned paths.
