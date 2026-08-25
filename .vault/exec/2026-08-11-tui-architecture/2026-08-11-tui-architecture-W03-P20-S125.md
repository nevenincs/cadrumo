---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:69076b0b5e6f9ca59b05ef364087c2b675ba039486d6a8f282f819b7ab4c8608'
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
- Corrected independent-review findings by embedding the exact canonical `CalculationSourceRef`; pinning every facet to V1, selected revision, schema identity/fingerprint, baseline, and contributor identities; preserving the exact readiness projection and registry closure limbs; binding capabilities to the exact resolved target; and expanding schema references for continuity, formula operands, relation endpoints, applicability, constraints, and export exposure.
- Promoted the existing canonical `ContinuidadId` through the `domain.calculations.registry` facade and its existing public-boundary assertion, without copying the declaration or changing concurrent registry edits.
- Replaced unsafe mixed fact values with strict discriminated text, count, and flag branches, and added adversarial coverage for each corrective boundary.

## Outcome

Corrected implementation is review-ready. The S125 checkbox remains open pending independent re-review. The public application facade and executable workspace service are deferred to their separately owned plan steps; this step adds neither a shim nor a cross-owner private import.

## Notes

Semantic RAG returned an incomplete code index warning for absent-result searches, so exact source census was used alongside positive semantic findings. The adjudicated existing owners were `ModeloWorkReview` for the review facet, `_work_addressing` for request targets, `CalculationSourceRef` for persisted source lineage, `ProjectionModeloReadiness` for readiness axes, `RegistryClosureLimb` for production closure facts, core for identity/authority/locale primitives, `domain.calculations.registry` for schema identities, and `application.operator_actions` for recovery references. No duplicate Workspace V1 model family was found in production `application.modelo` sources.

Corrective focused evidence: `uv run ruff check` passed; `uv run ty check` passed; `uv run pytest -q -o addopts='' -m integration src/cadrumo/application/modelo/tests/test_workspace_models.py` passed with 13 tests; `test_registry_casilla_continuity_reports_are_public_api` passed; `git diff --check` passed for owned paths.

The full registry public-boundary module remains red for pre-existing non-S125 debt: `test_unsupported_design_span_policy.py` imports private `cadrumo.domain.calculations.registry._authority` and `_errors`, which the global scanner reports. S125 neither introduced nor changes those imports, so this record does not claim the full module suite is green.
