---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-06-calculation-truth-registry-modelo-115-construct-workflow-closure-review-audit]]'
---

# Calculation Truth Registry Modelo 115 Construct Workflow Closure Execution

## Topic

Harden Modelo 115 so the quarterly rental-withholding registry revision exposes
one construct that owns the filing-grade workflow surfaces required by the
accepted calculation-truth-registry ADR.

## Audit Surface

- `registry/aeat/modelos/115.toml`
- `src/aeat/domain/calculations/registry/test_modelo_115_registry.py`
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Rewrite Scope

The slice is limited to Modelo 115 construct ownership, approval and
reconciliation workflow links, and focused registry behaviour tests. It does not
introduce compatibility aliases, generated rule inputs, or migration-state
assertions.

## ADR Grounding

The ADR requires registry data under `registry/aeat/`, strict validated
snapshots before calculation or filing workflow use, and Python code acting only
as loader, validator, executor, and tracer. Modelo 115 now declares the
quarterly withholding construct as the owner of its casillas, formulas,
parameter, export layout, extraction profiles, live/static evidence, workbook
layout reference, verification expectation, deadline windows, and application
links.

## Changes

- Added `modelo-115-quarterly-rental-withholding` as the construct for the
  supported revision.
- Added explicit snapshot-gated approval and reconciliation application links.
- Added focused behaviour tests for construct-owned workflow surfaces and the
  registry-backed withholding/result-to-pay formulas.
- Updated the plan ledger with the completed construct and focused test gate.

## Verification

- `uv run ruff format src/aeat/domain/calculations/registry/test_modelo_115_registry.py`
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_115_registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_115_registry.py`
- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_115_registry.py -q`
