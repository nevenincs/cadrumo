---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S398'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Supersede test_public_api_boundaries.py and test_architecture_boundaries.py now that the ratcheting scanner gate covers their checks, retiring the narrower assertions while keeping any check the scanner does not yet cover

## Scope

- `src/aeat/domain/calculations/registry/tests/test_public_api_boundaries.py`
- `src/aeat/entrypoints/cli/tests/test_architecture_boundaries.py`

## Description

- The originating Step row named a nonexistent path
  (`src/aeat/tests/test_public_api_boundaries.py`); the real files are the
  registry-package-scoped and CLI-package-scoped gates listed above.
- Read every check in both files line by line to classify each as either an
  import-hygiene duplicate (superseded by the new gate) or a distinct
  structural rule (kept):
  - Registry gate KEPT (not import-hygiene duplicates):
    `test_registry_ledger_binding_substrate_is_public_api` and
    `test_registry_casilla_continuity_reports_are_public_api` (positive
    facade-content assertions, not import checks),
    `test_source_tree_does_not_use_absolute_registry_private_imports` (a
    stricter, no-allowlist, intra-and-cross-package absolute-import ban the
    general gate does not replicate), and
    `test_modelo_registry_tests_use_public_registry_api_boundaries` (an
    intra-package test-boundary rule; Family-1 only flags cross-package
    imports).
  - Registry gate RETIRED (superseded):
    `test_production_code_does_not_import_raw_registry_orchestration` plus its
    dedicated helpers (`_raw_registry_orchestration_imports`,
    `_is_test_source`, `_module_name_for`, `_resolve_import_module`) and its
    `_RAW_REGISTRY_ORCHESTRATION_NAMES` / `_RAW_REGISTRY_ORCHESTRATION_MODULES`
    / `_RAW_REGISTRY_ORCHESTRATION_IMPORT_ALLOWLIST` constants. Verified by
    `rg` that none of the six allowlisted paths
    (`_authority.py`, both package `__init__.py` files, `legal_parameters.py`,
    `_imputacion_parameters.py`, `_recargo_equivalencia.py`) still import
    `build_snapshot` / `load_registry_tree` raw — every one now goes through
    the `registry.__init__` public facade or stays intra-package.
  - CLI gate KEPT (not import-hygiene duplicates):
    `test_extracted_modelo_cli_modules_do_not_import_legacy_modelo_root`,
    `test_legacy_modelo_root_does_not_add_private_backend_imports`,
    `test_legacy_modelo_root_does_not_add_registry_authority_reads`,
    `test_extracted_modelo_cli_modules_do_not_define_raw_id_regexes_outside_support`,
    `test_extracted_modelo_cli_modules_do_not_reintroduce_legacy_selector_calls`,
    `test_modelo_cli_uses_centralized_operator_addressing_facades` — these are
    modelo-CLI-decomposition-specific structural budgets (legacy-root growth,
    raw-id-regex placement, selector-call reintroduction, centralized-
    addressing bypass), not cross-package private-import checks.
  - CLI gate RETIRED (superseded):
    `test_extracted_modelo_cli_modules_do_not_import_private_application_modules`
    and `test_extracted_modelo_cli_modules_do_not_add_untracked_private_domain_imports`
    plus the `_PRIVATE_DOMAIN_IMPORT_EXCEPTIONS` allowlist (the two entries the
    dispatch brief named: `_modelo_iva_wallet_cli.py` -> `domain.iva_compensation._errors`
    and `_modelo_maritime_cli.py` -> `domain.renta._errors`). Verified by AST
    walk that neither modelo CLI module still imports its domain package's
    private submodule — both import the public facade
    (`domain.iva_compensation.IvaCompensationSeedConflictError`,
    `domain.renta.RentaValidationError`) today.
- Added a module docstring to each file naming the new gate, explaining which
  checks were retired and why, and confirming the retired allowlists were
  empty in practice at supersession time (no coverage silently dropped).
- Did NOT delete either file: the retired checks were the ONLY import-hygiene-
  duplicate assertions in each; every other check is a distinct structural
  rule this Wave has no charter to touch, and one of them
  (`test_extracted_modelo_cli_modules_do_not_reintroduce_legacy_selector_calls`)
  is currently red from unrelated, untouched peer work in
  `_modelo_work_verification_cli.py` — left exactly as found, per the
  full-tree-gate-must-distinguish-owner discipline.

## Outcome

`uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_public_api_boundaries.py -m unit`
passes 4/4 (was 5; the one retired test is gone, zero others affected).
`uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_architecture_boundaries.py -m integration`
passes 5/6, with the 6th (`test_extracted_modelo_cli_modules_do_not_reintroduce_legacy_selector_calls`)
failing identically before and after this Step's edits — confirmed via `git
status` that `_modelo_work_verification_cli.py` carries zero diff from this
Step, so the failure is pre-existing, unrelated peer work outside this Wave's
scope. `ruff check` / `ruff format --check` pass on both touched files.

## Notes

None.
