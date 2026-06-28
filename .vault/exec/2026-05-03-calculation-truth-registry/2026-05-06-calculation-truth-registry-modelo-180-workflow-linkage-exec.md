---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-06-calculation-truth-registry-modelo-180-workflow-linkage-review-audit]]'
---

# Calculation Truth Registry Modelo 180 Workflow Linkage Execution

## Topic

Close the Modelo 180 registry-backed workflow linkage row under the accepted
calculation-truth-registry ADR.

## Audit Surface

- `registry/aeat/modelos/180.toml`
- `src/aeat/domain/calculations/registry/test_modelo_180_registry.py`
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Rewrite Scope

The slice is limited to Modelo 180 annual-summary registry linkage and focused
behaviour tests. It does not add legacy aliases, generated registry inputs, or
transition-state assertions.

## ADR Grounding

The accepted ADR requires registry definitions under `registry/aeat/`, immutable
validated snapshots before calculation or filing workflow use, explicit
cross-model relations, and fail-fast handling of missing source observations.
Modelo 180 is an annual summary of Modelo 115 quarterly filings, so the
registry construct now owns the relation, calculation, export, parser,
verification, live/static reference, and workflow-facing application links for
both supported revisions.

## Changes

- Added snapshot-gated review, approval, reconciliation, and workflow
  application links for both Modelo 180 revisions.
- Attached Modelo 180 construct membership to extraction profiles, live/static
  references, workbook layout evidence, verification expectations, and all
  application links needed by filing-grade workflows.
- Added focused behaviour tests that load the real registry, build validated
  snapshots, resolve Modelo 115 quarterly observations into Modelo 180
  relations, calculate annual totals, and reject incomplete source-period
  chains.
- Updated the plan rows for the completed Modelo 180 workflow linkage and
  focused quality gate.

## Verification

- `uv run ruff format src/aeat/domain/calculations/registry/test_modelo_180_registry.py`
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_180_registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_180_registry.py`
- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_180_registry.py -q`
