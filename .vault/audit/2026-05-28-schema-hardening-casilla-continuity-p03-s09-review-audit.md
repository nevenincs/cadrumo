---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-05-28-schema-hardening-m100-continuity-inventory-research]]'
---



# `schema-hardening` Code Review

Reviewed P03.S09 implementation for scoped strict continuity validation on the
covered M100 surface.

No CRITICAL, HIGH, MEDIUM, or LOW findings.

Scope reviewed:

- `src/aeat/domain/calculations/registry/_validate_cross_revision.py`
- `src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/revision.toml`

Checks reviewed:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_fragmented_revision_directories_are_schema_owned -q`
- `uv run --no-sync python -` registry load probe for M100 strict revisions and `0582` continuity metadata.

Residual note: strict mode is scoped to declared continuity surfaces so M100 can
be hardened incrementally without masking that most M100 drift remains advisory.
