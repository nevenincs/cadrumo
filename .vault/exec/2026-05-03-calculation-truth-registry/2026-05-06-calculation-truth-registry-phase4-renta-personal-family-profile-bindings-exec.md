---
tags: ["#exec", "#calculation-truth-registry"]
date: "2026-05-06"
modified: '2026-05-06'
related:
  - "[[2026-05-03-calculation-truth-registry-rebuild-plan]]"
  - "[[2026-05-03-calculation-truth-registry-pending-adr]]"
---



# `calculation-truth-registry` `phase-4` `renta-personal-family-profile-bindings`

Expanded the Modelo 100 ejercicio 2025 `renta-personal-family` registry
construct from the initial identity/profile slice into the first taxpayer and
spouse profile binding slice.

- Modified: `registry/aeat/modelos/100.toml`
- Modified: `src/aeat/domain/profile/_keys.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- Modified: `src/aeat/entrypoints/cli/test_user_cli_surface.py`

## Description

The live registry now covers 11 `profile` bindings and 11 bound casillas for
the `renta-personal-family` construct. The casillas bind taxpayer identity,
CCAA, taxation type, taxpayer sex, marital status, taxpayer birth date, and
spouse identity fields. First taxpayer and declaration fields remain required;
spouse fields remain optional with selectors that record the joint-taxation
condition through `declaration.type == "2"`. The taxpayer marital-status
selector records the 2025 date axis with `valid_at = "2025-12-31"`.

The slice is grounded in `orden-hac-277-2026:art-3`,
`aeat-dr-100-2025-dictionary`, `aeat-dr-100-2025-xsd`, and
`boe-modelo-100-2025-form`. The profile remains a factual data source; it does
not own Modelo 100 legal treatment, formulas, minimums, quota transfer, or
family-unit calculations.

`PROFILE_KEYS` now exposes the added Modelo 100 taxpayer and spouse keys as
optional profile fields while preserving `tax.id` and `activity` as required
profile keys. The CLI surface test proves `setup profile list-keys` exposes
the accepted names and still excludes retired names.

This expands the earlier initial slice that covered `DPNIF_D`, `DP_APENOM_D`,
`ZCCAD`, and `TIPOTRIBUTACION`. The parent Renta personal/family plan row
remains open for family unit, descendants, ascendants, disability, dependency
conditions, minimums, formulas, and base/quota transfer.

## Tests

- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py::test_modelo_100_constructs_include_dependency_and_source_evidence_members src\aeat\domain\calculations\registry\test_modelo_100_registry.py::test_modelo_100_personal_family_profile_bindings_target_profile_schema src\aeat\domain\profile\test_keys.py src\aeat\application\profile\test_validate.py src\aeat\entrypoints\cli\test_user_cli_surface.py::test_profile_keys_match_domain_registry_names -q`
- `uv run python -m aeat.domain.calculations.registry._validate registry\aeat`
- `uv run ruff check src\aeat\domain\profile\_keys.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\entrypoints\cli\test_user_cli_surface.py`
- `uv run ty check src\aeat\domain\profile\_keys.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\entrypoints\cli\test_user_cli_surface.py`
