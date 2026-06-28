---
tags:
  - '#exec'
  - '#registry-reviewability-pressure'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - '[[2026-06-04-registry-reviewability-pressure-plan]]'
---

# `registry-reviewability-pressure` `P02.S03` split

Scope: split M123 inline-only revision directories into reviewable revision
fragments after S02 authorised the mechanical layout change.

## Description

- Split both M123 revisions by repeatable revision field group.
- Preserved scalar revision metadata in each `revision.toml`.
- Moved casillas, formulas, export layouts, extraction profiles, live cross
  references, workbook parity refs, verification expectations, constructs,
  application links, and 2024 deadline windows into field-group fragment files.
- Proved loaded `ModeloDefinition` equality before and after the split during
  the mechanical transformation.

## Outcome

S03 completed. M123 no longer owns the largest committed TOML file:
`123/revisions/2024-y-siguientes/revision.toml` dropped from 1,218 lines to 11
lines, and `123/revisions/2019-2023/revision.toml` dropped from 932 lines to 12
lines. The largest new M123 fragment is the 2024 export layout at 623 lines.

## Notes

Verification:

- Mechanical splitter compared `load_modelo_directory` output before and after
  on a temporary copy and on the real M123 directory.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q` passed: 27 tests.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_reviewability.py -q` passed: 3 tests.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py -q` passed: 41 tests.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_record_design.py -q` passed: 41 tests.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q` passed: 37 tests.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-registry-reviewability-pressure-plan.md` passed.
