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

Reviewed P03.S08 implementation for the first M100 continuity metadata slice.

No CRITICAL, HIGH, MEDIUM, or LOW findings.

Scope reviewed:

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/casillas/0553-0582.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/casillas/0562-0582.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0564-0582.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0648-0582.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/continuidad/0582-2022-2023-unchanged.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/continuidad/0582-2023-2024-unchanged.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/continuidad/0582-2024-2025-unchanged.toml`

Checks reviewed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_fragmented_revision_directories_are_schema_owned src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_directory_source_inventory_lists_every_revision_fragment_toml -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_cross_revision_validator_accepts_committed_corpus src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_backend_registry_validation_accepts_committed_corpus_drift_gate -q`
- `uv run --no-sync python -` registry load probe for M100 `0582` continuity ids and evolution counts.

Residual note: strict M100 validation remains intentionally disabled because
uncovered M100 drift remains large outside this first continuity chain.
