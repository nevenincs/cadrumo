---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-06-calculation-truth-registry-modelo-123-construct-workflow-closure-review-audit]]'
---

# Calculation Truth Registry Modelo 123 Construct Workflow Closure Execution

## Topic

Harden Modelo 123 so current and historical capital-income withholding revisions
own their filing-grade workflow surfaces through central registry constructs.

## Audit Surface

- `registry/aeat/modelos/123.toml`
- `src/aeat/domain/calculations/registry/test_modelo_123_registry.py`
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Rewrite Scope

The slice is limited to Modelo 123 construct ownership, missing workflow
application links, and focused registry behaviour tests. It does not introduce
legacy adapters, compatibility aliases, generated rule inputs, or old-state
assertions.

## ADR Grounding

The accepted calculation-truth-registry ADR requires reviewed TOML definitions,
strict validated snapshots before calculation or workflow use, one registry
authority for modelo/casilla/formula truth, and no Python-side legal shadowing.
Modelo 123 now exposes construct-scoped current and 2019-2023 revisions, each
owning its casillas, formulas, layouts, extraction profiles, live/static
evidence, workbook references, verification expectations, and application links.

## Changes

- Added current and 2019-2023 Modelo 123 construct definitions.
- Added snapshot-gated approval and reconciliation links for the current
  revision.
- Added snapshot-gated review, approval, reconciliation, and workflow links for
  the 2019-2023 revision.
- Added focused behaviour tests for construct workflow ownership and current
  plus historical formula execution.
- Updated the plan ledger with the completed construct and focused test gate.

## Verification

- `uv run ruff format src/aeat/domain/calculations/registry/test_modelo_123_registry.py`
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_123_registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_123_registry.py`
- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_123_registry.py -q`
