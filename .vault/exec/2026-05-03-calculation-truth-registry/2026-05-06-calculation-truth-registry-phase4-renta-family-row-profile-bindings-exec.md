---
tags: ["#exec", "#calculation-truth-registry"]
date: "2026-05-06"
modified: '2026-05-06'
related:
  - "[[2026-05-03-calculation-truth-registry-rebuild-plan]]"
  - "[[2026-05-03-calculation-truth-registry-pending-adr]]"
  - "[[2026-05-05-modelo-100-renta-source-dependency-reference]]"
---



# `calculation-truth-registry` `phase-4` `renta-family-row-profile-bindings`

Expanded the Modelo 100 ejercicio 2025 `renta-personal-family` slice from
scalar taxpayer/spouse profile fields into typed repeated descendant and
ascendant profile-row bindings.

- Modified: `registry/aeat/modelos/100.toml`
- Modified: `src/aeat/domain/profile/__init__.py`
- Created: `src/aeat/domain/profile/family.py`
- Created: `src/aeat/domain/profile/test_family.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`

## Description

The registry now declares official Modelo 100 descendant row fields
`NIFDLG`, `APENOMDLG`, `FNACDLG`, `MINUSDLG`, and `FALLDLG`, and ascendant row
fields `DNIASDLG`, `APENOMDLG_ASC`, `ANOASDLG`, `PCTMINASDLG`, `CONVASDLG`,
and `FALLASDLG` under the `renta-personal-family` construct.

Each row field is a bound casilla backed by a profile binding whose selector
names `RentaFamilyProfile`, the official collection, the typed field, the XSD
path, and the dictionary field. The implementation intentionally avoids
numbered synthetic family-member keys. Python now owns only strict factual row
validation through `RentaDescendantProfile`, `RentaAscendantProfile`, and
`RentaFamilyProfile`; legal treatment, minimums, deductions, and formula
transfer remain owned by Modelo 100 registry data.

This keeps the parent Renta personal/family plan row open for legal minimums,
dependency conditions, state/autonomous quota transfer, and observed artefact
parsing.

## Tests

- `uv run python -m aeat.domain.calculations.registry._validate registry\aeat`
- `uv run pytest src\aeat\domain\profile\test_family.py src\aeat\domain\profile\test_keys.py src\aeat\application\profile\test_validate.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\entrypoints\cli\test_user_cli_surface.py::test_profile_keys_match_domain_registry_names -q`
- `uv run ruff check src\aeat\domain\profile\__init__.py src\aeat\domain\profile\family.py src\aeat\domain\profile\test_family.py src\aeat\domain\profile\_keys.py src\aeat\domain\profile\test_keys.py src\aeat\application\profile\test_validate.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\entrypoints\cli\test_user_cli_surface.py`
- `uv run ty check src\aeat\domain\profile\__init__.py src\aeat\domain\profile\family.py src\aeat\domain\profile\test_family.py src\aeat\domain\profile\_keys.py src\aeat\domain\profile\test_keys.py src\aeat\application\profile\test_validate.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\entrypoints\cli\test_user_cli_surface.py`
