---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---

# Modelo 131 2024 And 2025 Revision Step

## Scope

- Add explicit Modelo 131 registry revisions for 2024 and 2025.
- Keep 2019-2023 open until its annual module-order legal trail is catalogued.
- Avoid export support changes until DPA, DID, and the historical flatter record
  layout are represented as distinct structures.

## Changes

- Added 2024 and 2025 revisions to `registry/aeat/modelos/131.toml`.
- Added year-scoped legal references for the 2024 and 2025 annual module orders.
- Added year-scoped workbook-layout references and verification expectations.
- Added the 2019, 2020, 2021, 2022, and 2023 BOE module orders to the normative
  corpus and legal catalogue.
- Added the 2019-2023 Modelo 131 revision with the flatter historical
  record-design source and historical calculation formulas.
- Extended committed-registry behaviour coverage to prove 2024, 2025, and 2026
  revision selection and liquidacion calculations.
- Extended committed-registry behaviour coverage to prove the 2019 and 2023
  historical revision boundaries.
- Updated the plan ledger to mark 2019-2023, 2024, and 2025 revision work
  complete while keeping export, live fixture, and whole-tree verification rows
  open.

## Verification

- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py -q`
- `uv run ruff check registry\aeat\modelos\131.toml src\aeat\domain\calculations\registry\test_committed_registry.py`
- `uv run ty check src\aeat\domain\calculations\registry\test_committed_registry.py`
- `uv run python -` with `RegistryValidator(...).validate_modelo(modelo_131)`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
