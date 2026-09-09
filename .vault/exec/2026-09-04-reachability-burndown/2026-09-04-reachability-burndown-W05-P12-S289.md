---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:f77c0e00989bc90d4d514d6e1c719218b3c32882e429b30550a8d05d964c31b3'
step_id: 'S289'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the production modelo authorization/enrollment regime and its source-parsing gates; retain direct cross-year calculation, persistence, and registry behavior tests without copied implementation text or development-status manifests.

## Scope

- `authorization runtime/data/locales`
- `conformance projections`
- `enrollment recorder/tests`
- `retained cross-year behavior tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

- `D` `src/cadrumo/core/access_gate/authorization.py`
- `D` `src/cadrumo/_data/registry/aeat/authorization.d/`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/domain/calculations/registry/_loader_internals.py`
- `M` `src/cadrumo/application/modelo/calculate_input.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`
- `M` `src/cadrumo/application/calculations/multi_year.py`
- `M` `src/cadrumo/application/calculations/__init__.py`
- `D` `src/cadrumo/core/access_gate/tests/test_authorization_manifest.py`
- `D` `src/cadrumo/core/tests/test_modelo_authorization_gate.py`
- `D` `src/cadrumo/entrypoints/cli/tests/test_modelo_authorization_advisory_banner.py`
- `D` `src/cadrumo/application/calculations/tests/test_multi_year_recorder.py`
- `D` `src/cadrumo/application/calculations/tests/test_enrollment_recorder_context_mode_guard.py`
- `D` `src/cadrumo/application/calculations/tests/test_calculation_refusal_message_key_only.py`
- `M` `src/cadrumo/application/calculations/tests/`
- `R` `src/cadrumo/application/calculations/tests/test_modelo_100_multiyear_renta_enrollment.py -> src/cadrumo/application/calculations/tests/test_modelo_100_cross_year_carry_continuity.py`
- `R` `src/cadrumo/application/calculations/tests/test_modelo_130_multiyear_renta_enrollment.py -> src/cadrumo/application/calculations/tests/test_modelo_130_cross_year_carry_continuity.py`
- `M` `src/cadrumo/tests/registry_conformance.py`
- `M` `dev/registry/conformance/manager.py`
- `M` `dev/registry/conformance/cli.py`
- `M` `src/cadrumo/core/errors/registry/`
- `M` `src/cadrumo/locales/`
- `M` `src/cadrumo/_data/registry/aeat/modelos/136/revisions/2026/revision.toml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check <focused authorization/conformance/calculation surface>` -> `pass`
- `verify:` `pytest --collect-only` retained calculation/conformance/registry surface -> `774 collected`
- `verify:` retained behavior surface -> `202 passed, 10 unrelated M303 fixture failures; 2 source-census failures removed with their tests`
- `verify:` exact authorization/enrollment production search -> `no matches`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `249 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

The focused run retains ten pre-existing M303 reds: eight observation fixtures omit the now-required filing disposition, and two synthetic CalculationRevision fixtures omit registry_snapshot_ref. Three conformance closure CLI cases also return no rendered report; their failures are outside this authorization-metastate removal.
