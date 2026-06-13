---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P09.S42'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P09.S42`

Closed GEN-6 task 521 as an explicit manual-supply disposition for the
Modelo 100 estimacion-directa binding.

- Updated: `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/bindings/0001-renta-2020-modelo-100-estimacion-directa-es-normal.toml`
- Updated: `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/bindings/0001-renta-2021-modelo-100-estimacion-directa-es-normal.toml`
- Updated: `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-renta-2022-modelo-100-estimacion-directa-es-normal.toml`
- Updated: `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/bindings/0001-renta-2023-modelo-100-estimacion-directa-es-normal.toml`
- Updated: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/0001-renta-2024-modelo-100-estimacion-directa-es-normal.toml`
- Updated: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/bindings/0001-renta-2025-modelo-100-estimacion-directa-es-normal.toml`
- Updated: `src/aeat/domain/calculations/registry/test_schema_hygiene.py`

## Description

Re-confirmed the overlap with BIND-5: profile-source bindings already
auto-resolve, but `renta-{year}-modelo-100-estimacion-directa-es-normal`
is not a profile-source binding. It is a `manual_input` binding for
casilla `0168`, typed as `EstimacionDirectaModalidad`, and the formula
graph consumes it as a Decimal boolean operand.

The registry disposition is therefore manual supply, not profile
auto-inference from `irpf.estimation_regime`. Added an explicit TOML
comment to every Modelo 100 revision binding and a registry hygiene
test that guards the source, selector, typed enum, source refs, and
source citations across all Renta revisions.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/test_schema_hygiene.py src/aeat/application/modelo/test_profile_binding.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/entrypoints/cli/test_modelo_discovery_defects.py` passed.

`uv run pytest src/aeat/domain/calculations/registry/test_schema_hygiene.py::test_renta_estimacion_directa_manual_supply_disposition_is_explicit src/aeat/domain/calculations/registry/test_schema_hygiene.py::test_renta_typed_binding_candidates_declare_substrate_enum_class src/aeat/application/modelo/test_profile_binding.py::test_estimacion_directa_binding_stays_in_the_decimal_channel src/aeat/application/modelo/test_profile_binding.py::test_estimacion_directa_binding_rejected_through_enum_channel src/aeat/domain/calculations/registry/test_queries.py::test_binding_rows_report_decimal_input_channel_for_typed_enum_binding src/aeat/entrypoints/cli/test_modelo_discovery_defects.py::test_bindings_list_marks_decimal_consumed_typed_enum_binding -q` passed with 6 tests in 43.15s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S42` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P09-S42.md src/aeat/domain/calculations/registry/test_schema_hygiene.py src/aeat/_data/registry/aeat/modelos/100/revisions/2020/bindings/0001-renta-2020-modelo-100-estimacion-directa-es-normal.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2021/bindings/0001-renta-2021-modelo-100-estimacion-directa-es-normal.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-renta-2022-modelo-100-estimacion-directa-es-normal.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2023/bindings/0001-renta-2023-modelo-100-estimacion-directa-es-normal.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/0001-renta-2024-modelo-100-estimacion-directa-es-normal.toml src/aeat/_data/registry/aeat/modelos/100/revisions/2025/bindings/0001-renta-2025-modelo-100-estimacion-directa-es-normal.toml` passed; Git repeated the pre-existing CRLF notice for the plan file.
