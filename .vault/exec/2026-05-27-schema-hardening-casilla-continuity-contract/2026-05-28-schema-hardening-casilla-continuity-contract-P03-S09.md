---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S09'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
---



# `schema-hardening` `P03.S09`

Enabled strict continuity validation for the covered M100 `0582` surface.

- Modified: `src/aeat/domain/calculations/registry/_validate_cross_revision.py`
- Modified: `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/revision.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/revision.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/revision.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/revision.toml`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p03-s09-review.md`

## Description

Adjusted strict continuity validation so revision-level strict mode enforces
only declared continuity surfaces: a divergence is in scope when either side
declares `continuidad_id` or a matching evolution declaration exists. This
allows M100 to opt into strict validation for the authored `0582` chain without
turning the still-advisory remainder of M100 into hard failures.

Set `continuidad_validation = "strict"` on M100 revisions `2022`, `2023`,
`2024`, and `2025`.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_fragmented_revision_directories_are_schema_owned -q`
- `uv run --no-sync python -` registry load probe for M100 strict revisions and `0582` continuity metadata.

The full cross-revision drift test passed with four existing singleton
semantic-role warnings for M347.
