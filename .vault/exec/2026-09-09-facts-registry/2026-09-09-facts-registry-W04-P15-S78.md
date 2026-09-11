---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:837ebbe87279f7866e7d684da509a2b7e5b8e16197c9c2080f7f3d9489e89a24'
step_id: 'S78'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Normalize and retire the legal-holiday calendar adapter while preserving publication and event provenance

## Scope

- `src/cadrumo/_data/registry/aeat/calendars and src/cadrumo/_data/registry/aeat/facts and dev/registry/compiler/holidays.py and dev/registry/compiler/fact_providers.py and dev/registry/tests`

## Changes

- `M` `dev/registry/analysis/facts_wave2_provider_handoff.toml`
- `M` `dev/registry/compiler/fact_providers.py`
- `D` `dev/registry/compiler/holidays.py`
- `D` `dev/registry/tests/test_category_holiday_compiler_behavior.py`
- `A` `dev/registry/tests/test_facts_holiday_calendar_retirement.py`
- `M` `dev/registry/tests/test_facts_wave2_provider_handoff.py`
- `D` `src/cadrumo/_data/registry/aeat/calendars/festivos-2024.toml`
- `D` `src/cadrumo/_data/registry/aeat/calendars/festivos-2025.toml`
- `D` `src/cadrumo/_data/registry/aeat/calendars/festivos-2026.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0066-holiday-calendar-publication.toml`
- `A` `src/cadrumo/_data/registry/aeat/facts/0067-public-holiday.toml`
- `M` `src/cadrumo/application/aggregation/tests/test_structurally_unroutable_iva_base_categories.py`
- `D` `src/cadrumo/core/resources/_repos/tests/test_every_shipped_resource_loads.py`
- `M` `src/cadrumo/core/tests/test_resources.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_modelo_353_registry.py`
- `M` `src/cadrumo/domain/deadlines/festivos.py`
- `M` `src/cadrumo/domain/deadlines/tests/test_festivos.py`
- `verify:` `uv run --no-sync ruff check dev/registry/compiler/fact_providers.py dev/registry/tests/test_facts_holiday_calendar_retirement.py dev/registry/tests/test_facts_wave2_provider_handoff.py src/cadrumo/domain/deadlines/festivos.py src/cadrumo/domain/deadlines/tests/test_festivos.py src/cadrumo/core/tests/test_resources.py src/cadrumo/application/aggregation/tests/test_structurally_unroutable_iva_base_categories.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_facts_holiday_calendar_retirement.py dev/registry/tests/test_facts_wave2_provider_handoff.py dev/registry/tests/test_wave2_fact_provider_handoff.py` -> `pass`

## Notes

- Full deadline-domain tests remain blocked before collection by the pre-existing absence of `src/cadrumo/_data/registry/authority/authority.json`; no retired calendar source is used as a fallback.
