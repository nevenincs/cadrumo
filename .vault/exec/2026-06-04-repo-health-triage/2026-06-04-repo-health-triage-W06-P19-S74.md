---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S74'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W06.P19.S74 modelo CLI command complexity reduction

Scope: `W06.P19.S74` - Reduce remaining modelo CLI command cognitive
complexity.

## Description

- Extract bindings-list target query selection into `_bindings_report_for_target`.
- Extract bindings-list payload/text row projection into
  `_binding_list_rows_for_report`.
- Extract work-calculate CLI input parsing and decimal option coercion into
  `_work_calculate_input_bundle_from_cli` and `_optional_decimal_option`.
- Extract work-calculate saved/advisory output assembly into private helpers.
- Extract work-amend required-option, amendment-kind, and casilla-override
  parsing into private helpers.

## Outcome

Completed. The touched command callbacks are no longer C-level Radon hotspots:
`bindings_list` is B (10), `work_calculate` is A (4), and `work_amend` is below
the high-complexity list. Complexipy reports no `_modelo.py` function above the
project threshold of 20.

Verification:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py` passed.
- `uv run --no-sync radon cc src/aeat/entrypoints/cli/_modelo.py -s` captured
  the reduced command callback grades.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_bindings_list_missing_filter.py src/aeat/entrypoints/cli/test_work_calculate_borrador.py src/aeat/entrypoints/cli/test_modelo_work_ux.py::test_work_calculate_confirms_the_draft_was_saved src/aeat/entrypoints/cli/test_modelo_discovery_defects.py::test_bindings_list_missing_drops_profile_resolved_bindings src/aeat/entrypoints/cli/test_modelo_discovery_defects.py::test_bindings_list_year_resolves_the_year_covering_revision src/aeat/entrypoints/cli/test_modelo_discovery_defects.py::test_work_calculate_leads_with_a_result_summary -q`
  passed with 9 tests.
- `uv run --no-sync python -c "from typer.testing import CliRunner; from aeat.entrypoints.cli import app; r=CliRunner().invoke(app, ['app','modelo','work','amend','--help']); print(r.exit_code); print('from-filing-record' in r.output, '--kind' in r.output, '--set' in r.output)"`
  printed exit code 0 and `True True True`.
- `uv run --no-sync python -m compileall -q src/aeat/entrypoints/cli/_modelo.py`
  passed.

## Notes

`ty check` over `_modelo.py` still reports 26 pre-existing diagnostics in
row-splat and revision-object typing areas. This step did not broaden into a
full modelo CLI type cleanup.
