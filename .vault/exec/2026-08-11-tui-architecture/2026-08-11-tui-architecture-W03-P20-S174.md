---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:b338310e9a700f00a61c827aa763aa6cb21cc29f79f9142c7b651c97dcc10332'
step_id: 'S174'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Define in the sole public application/modelo/work_addressing.py module one pure application revision assertion that evaluates the independent S125 requested and stored axes against the law-selected revision from exactly one S159 RegistryAuthorityCapture, atomically migrate every addressing, work-review, calculation, external-import, quickfile, lifecycle, CLI, registration, test, dynamic, and tooling consumer to direct defining-module imports, and delete resolve_registry_revision_for_work_target, every package binding, load_registry_tree, asserted-ID selection, stale docstring reference, and parallel registry read from the work path with fixed-point proof and no shim, alias, fallback, bridge, or re-export

## Scope

- `src/cadrumo/application/modelo/work_addressing.py`
- `src/cadrumo/application/modelo/_calculation_helpers.py`
- `src/cadrumo/application/modelo/work_review_projection.py`
- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/application/modelo/_external_import_actions.py`
- `src/cadrumo/application/modelo/_quickfile.py`
- `src/cadrumo/application/modelo/_work_lifecycle.py`
- `src/cadrumo/application/modelo/__init__.py inert-namespace gate`
- `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`
- `src/cadrumo/entrypoints/cli/_config/_profile_inspect.py`
- `every affected registration/test/dynamic/tooling consumer`
- `and focused revision-identity/direct-defining-module fixed-point tests`

## Changes

- `M` `src/cadrumo/application/modelo/work_addressing.py`
- `M` `src/cadrumo/application/modelo/_calculation_helpers.py`
- `M` `src/cadrumo/application/modelo/_quickfile.py`
- `M` `src/cadrumo/application/modelo/_work_lifecycle.py`
- `M` `src/cadrumo/application/modelo/external_import_actions.py`
- `M` `src/cadrumo/application/modelo/work_review_projection.py`
- `M` `src/cadrumo/application/modelo/tests/test_revision_id_d1_contract.py`
- `M` `src/cadrumo/application/calculations/tests/test_revision_id_no_injection_regression.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_profile_inspect.py`
- `M` `src/cadrumo/entrypoints/cli/_config/tests/test_preflight_revision_ambiguity_refusal.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`
- `M` `src/cadrumo/entrypoints/cli/tests/_modelo_review_package_support.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_config_preflight_revision_default.py`
- `M` `src/cadrumo/tests/modelo_work_review.py`
- `M` `src/cadrumo/tests/registry_revision.py`
- `M` `src/cadrumo/tests/test_relative_imports_only.py`
- `M` `.vaultspec/rules/aeat-registry-authority-flow.md`
- `M` `.claude/rules/aeat-registry-authority-flow.md`
- `M` `.agents/rules/aeat-registry-authority-flow.md`
- `M` `.codex/rules/aeat-registry-authority-flow.md`
- `M` `.gemini/rules/aeat-registry-authority-flow.md`
- `verify:` `pytest test_revision_id_d1_contract.py test_revision_id_no_injection_regression.py test_work_addressing.py` -> `pass`

## Notes

The surrounding `application/modelo/tests/` suite carries four failures
(`test_actions.py` x3, `test_amend_flow.py` x1). A clean HEAD worktree
reproduces the identical four failures with the identical 61 passed, so they
predate this Step and are unrelated to revision resolution.

`test_relative_imports_only` reports 2066 absolute intra-cadrumo imports
tree-wide, overwhelmingly `cadrumo.domain.calculations.registry.*` fallout from
the c94133f public-module relocation. Out of scope here; it belongs to the
registry facade family work.
