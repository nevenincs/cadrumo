---
tags: ["#exec", "#cli-testimonial"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P01.S01-P01.S04'
related:
  - '[[2026-05-21-fresh-cli-persona-repair-plan]]'
  - '[[2026-05-21-fresh-cli-persona-findings-inventory-audit]]'
---

# `fresh-cli-persona-repair` `P01.S01-P01.S04`

Addressed the verified small CLI defects from the fresh persona wave.

- Retired/guarded the direct legal-entity-form parsing finding after it
  no longer reproduced in shell and the existing regression test passed.
- Fixed `casillas --form-number` so it matches the printed numeric
  `number` column as well as explicit `form_number` metadata.
- Fixed the Modelo export recovery hint to name
  `aeat app modelo work verify`.
- Added focused regression coverage for the casilla-number and export
  recovery surfaces.

## Tests

`uv run python -m aeat.locales scaffold` updated the locale catalogue
for the new export recovery translation key.

`uv run ruff check src/aeat/domain/calculations/registry/_queries.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_modelo_work_ux.py src/aeat/entrypoints/cli/test_profile_create_taxpayer_type_paths.py` passed.

`uv run pytest src/aeat/entrypoints/cli/test_modelo.py::test_casillas_form_number_filter_matches_declared_casilla src/aeat/entrypoints/cli/test_modelo.py::test_casillas_form_number_filter_matches_printed_number src/aeat/entrypoints/cli/test_modelo_work_ux.py::test_modelo_export_unverified_work_unit_points_to_work_verify src/aeat/entrypoints/cli/test_profile_create_taxpayer_type_paths.py::test_legal_entity_form_flag_populates_the_legal_entity_form_field -q` passed with 4 tests in 22.88s.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Shell rechecks passed:

- `uv run aeat app modelo casillas 303 --period 1T --form-number 69`
  returned `iva.resultado	69	computed	false	Resultado de la autoliquidacion`.
- `uv run aeat config profile create sl-co --quiet --accept-defaults --entity-type legal_entity --legal-entity-form sl --tax-id B66012345 --activity comercio` succeeded.
- `uv run aeat app modelo export <work-unit-id> --output ...` on an
  unverified work unit refused with `Run aeat app modelo work verify
  first`.
