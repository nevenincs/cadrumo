---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S08'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
---



# `schema-hardening` `P03.S08`

Authored the first minimal M100 continuity metadata slice.

- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/casillas/0553-0582.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/casillas/0562-0582.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0564-0582.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0648-0582.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/continuidad/0582-2022-2023-unchanged.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/continuidad/0582-2023-2024-unchanged.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/continuidad/0582-2024-2025-unchanged.toml`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p03-s08-review.md`

## Description

Added `continuidad_id = "irpf.intereses-demora-regularizacion.estatal"` to
M100 casilla `0582` for revisions `2022` through `2025`. Added three
`unchanged` evolution declarations for the adjacent revision pairs
`2022->2023`, `2023->2024`, and `2024->2025`.

This slice intentionally leaves M100 in advisory mode. Strict validation is
not enabled here because the rest of M100 still contains large uncovered annual
drift.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_fragmented_revision_directories_are_schema_owned src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_directory_source_inventory_lists_every_revision_fragment_toml -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_cross_revision_validator_accepts_committed_corpus src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_backend_registry_validation_accepts_committed_corpus_drift_gate -q`
- `uv run --no-sync python -` registry load probe for M100 `0582` continuity ids and evolution counts.

The committed-corpus validation check passed with four existing singleton
semantic-role warnings for M347.
