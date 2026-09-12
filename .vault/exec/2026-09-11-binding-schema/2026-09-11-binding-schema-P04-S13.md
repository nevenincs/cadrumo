---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:3ac0d2f9a2485f7bedd8d691485049527818dbebd729eb11ad1b008ea13986af'
step_id: 'S13'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Retire the ROWS exemption in favour of registration disposition, delete legacy single-file loader branches, and remove the three discriminated-union docstrings

## Scope

- `src/cadrumo/application/modelo/calculation_actions.py`
- `dev/registry/compiler/_loader_internals.py`
- `dev/registry/compiler/loader.py`

## Changes

- `M` `dev/registry/compiler/_loader_internals.py`
- `M` `dev/registry/compiler/loader.py`
- `M` `dev/registry/compiler/loader_cache.py`
- `M` `dev/registry/maintenance_support.py`
- `M` `dev/registry/conformance/loader_directory_mode_support.py`
- `M` `dev/registry/conformance/tests/test_registry_schema_part1.py`
- `M` `dev/registry/tests/test_loader_directory_mode.py`
- `M` `dev/registry/tests/test_loader_directory_fragments.py`
- `M` `dev/registry/tests/test_deadline_window_loader.py`
- `M` `dev/registry/tests/test_loader_fingerprint_content_collision.py`
- `M` `dev/registry/tests/test_loader_cache_isolation.py`
- `M` `dev/registry/tests/test_semantic_map_join.py`
- `M` `dev/registry/pipeline/test_generated_tree_check.py`
- `M` `dev/registry/pipeline/test_generated_export_tree_validation.py`
- `verify:` `uv run ruff check <touched>` -> `pass`
- `verify:` `uv run ty check <touched>` -> `pass`
- `verify:` `uv run pytest dev/registry/tests/test_loader_directory_mode.py dev/registry/tests/test_loader_directory_fragments.py dev/registry/tests/test_deadline_window_loader.py dev/registry/tests/test_loader_fingerprint_content_collision.py -n 0` -> `fail`

## Notes

Three pre-existing failures remain in `test_loader_directory_mode.py`
(`test_shared_catalogues_reject_noncanonical_parameter_key`,
`test_shared_catalogues_preserves_valid_parameter_key_identity`,
`test_registry_tree_rejects_parameter_unknown_legal_refs`): they assert on the
retired global `[parameters]` catalogue section, which the loader already
refuses, and they are untouched by this step. Further pre-existing failures in
`test_registry_schema_part1.py` and `test_committed_registry.py` come from the
in-flight binding provider/value schema change, not from the layout retirement.

Two test modules under `src/` import `selector_model_for_source` from
`domain.calculations.registry.bindings`, where no such symbol is defined:
`src/cadrumo/domain/calculations/registry/tests/test_filing_grade_binding_resolution.py`
and `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`. Reported
rather than fixed; this step does not edit `src/`.
