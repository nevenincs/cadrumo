---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-hardening-m200-export-pressure-audit]]'
  - '[[2026-06-02-registry-hardening-next-work-P01-S08]]'
---

# P01.S08 Review

## Findings

No findings.

The change is a mechanical split of one M200 export record-field fragment. It
does not add loader behavior, schema behavior, or validation behavior. The
replacement files use the existing repeated layout-id and record-id pattern that
the directory-mode loader already merges by record id.

## Residual Risk

The largest committed TOML fragment is now M200 page 043 at 1612 lines. That
pressure remains tracked by the plan through the M200/M303 reviewability work.

An unrelated M200 parameter file was dirty in the shared worktree and was not
staged or committed with this slice.

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_directory_mode_merges_export_record_field_fragments_by_record_id -q`
  - Result: 1 passed in 0.30s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable -q`
  - Result: 2 passed in 6.28s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_tree_loads_directory_modelos -q`
  - Result: 1 passed in 29.27s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_directory_source_inventory_lists_every_revision_fragment_toml -q`
  - Result: 1 passed in 22.38s.
