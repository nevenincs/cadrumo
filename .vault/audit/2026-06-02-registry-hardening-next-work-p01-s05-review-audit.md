---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-hardening-next-work-P01-S05]]'
---

# P01.S05 Review

## Findings

No findings.

The change is a mechanical directory-mode split of the M100 2021 completeness
manifest. The generated fragments reconstruct the deleted file exactly in
sorted loader order, and the committed loader/reviewability tests pass.

## Residual Risk

M100 2020 still has an oversized completeness manifest and remains tracked by
`P01.S06`.

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_directory_mode_merges_completeness_manifest_casilla_fragments -q`
  - Result: 1 passed in 0.29s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable -q`
  - Result: 2 passed in 5.61s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_tree_loads_directory_modelos -q`
  - Result: 1 passed in 34.56s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_directory_source_inventory_lists_every_revision_fragment_toml -q`
  - Result: 1 passed in 26.11s.
