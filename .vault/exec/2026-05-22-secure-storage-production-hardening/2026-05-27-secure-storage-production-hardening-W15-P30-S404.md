---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S404'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W15.P30.S404`

Repaired the Modelo validation boundary by aligning strict output schemas and typed payload projections with the real create and calculate command lanes.

- Modified: `src/aeat/entrypoints/cli/_modelo_payloads.py`
- Modified: `src/aeat/entrypoints/cli/_modelo.py`
- Modified: `src/aeat/entrypoints/cli/test_modelo_work_ux.py`
- Modified: `src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py`
- Modified: `src/aeat/entrypoints/cli/test_modelo_compare.py`
- Modified: `src/aeat/entrypoints/cli/test_modelo_projection.py`

## Description

`WorkCreateResult.name_applied` is now nullable, matching the command behavior where the field is only populated when an idempotent create applies a supplied `--name` as a rename.

The calculation revision payload projection now normalizes strict schema fields before validation:

- observation collections are emitted as tuples for tuple-typed schema fields
- operand values are stringified before crossing the JSON contract boundary
- binding override values are stringified to match `dict[str, str]`
- result-summary rows are emitted as a tuple for the typed output contract

The affected real-CLI tests now unwrap the migrated success envelope for `modelo.work.*` commands, while still accepting bare payloads from non-migrated command surfaces. The work UX test pins that create and reuse-with-same-name both emit `name_applied: null`.

## Tests

Targeted verification:

- `uv run pytest -q src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py::test_bare_numeric_unknown_casilla_surfaces_helpful_message src/aeat/entrypoints/cli/test_modelo_work_ux.py::test_idempotent_work_create_reports_reuse`
- `uv run pytest -q src/aeat/entrypoints/cli/test_modelo_calculation_through_real_cli.py::test_modelo_130_resultado_apartado_i_direct_estimation`

Both targeted checks passed after the repair.
