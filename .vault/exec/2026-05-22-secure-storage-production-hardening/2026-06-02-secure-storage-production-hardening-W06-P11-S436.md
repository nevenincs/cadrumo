---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S436'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W06.P11.S436`

## Description

- Fixed relation prefill so missing prior filings degrade only the affected relation requirement.
- Preserved independently resolvable relation values instead of letting one missing same-model prior filing blank all relation cells.
- Exported `RegistryRelationSourceRequirement` through the registry package so application code stays on the public domain boundary.

## Outcome

Closed.

The Modelo 202 2P quota-base continuity test now resolves the available Modelo 200 relation even when the same-model prior-pagos relation remains operator-manual.

Validation:

- `uv run --no-sync pytest -q src/aeat/application/calculations/test_relation_prefill_source_mesh.py src/aeat/application/calculations/test_modelo_202_cuota_base_ejercicio_anterior_continuity.py` passed 6 tests.
- `uv run --no-sync ruff check src/aeat/application/calculations/_relation_prefill.py src/aeat/domain/calculations/registry/__init__.py src/aeat/application/calculations/test_relation_prefill_source_mesh.py src/aeat/application/calculations/test_modelo_202_cuota_base_ejercicio_anterior_continuity.py` passed.
