---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S435'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W06.P11.S435`

## Description

- Fixed the Modelo 202 quota-base registry wiring that blocked registry-backed calc-sheets validation.
- Attached the new quota-base binding, 2P/3P relation, and dependency classification to `modelo-202-foundation`.
- Kept the 1P relation undeclared because Modelo 200 currently has no pre-2024 source revision coverage; the registry must not silently bind 1P to the wrong ejercicio.
- Opened `W06.P11.S438` so the 1P source-coverage gap is plan-owned rather than left as a note.
- Added Modelo 202 registry assertions for the binding, dependency classification, and 2P/3P relation.

## Outcome

Closed.

Validation:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_modelo_202_registry.py` passed 3 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/domain/calculations/registry/test_modelo_202_registry.py` passed 5 tests.
- `uv run --no-sync ruff check` passed for the touched Modelo 202 registry test and TOML files.

## Notes

The 1P legal hook remains intentionally outside the declared relation set until source Modelo 200 history is modelled or an explicit registry gate is added. `W06.P11.S438` owns that work; S435 only closes the declared 2P/3P registry wiring blocker.
