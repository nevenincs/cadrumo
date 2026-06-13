---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m036-standardization-plan]]'
---



# `schema-hardening-m036-standardization` `P01.S03`

Verified the Modelo 036 directory-fragment layout against the focused
registry, census foundation, query, loader, and parser-fixture surfaces.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m036-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m036-standardization/2026-05-27-schema-hardening-m036-standardization-P01-S03.md`

## Description

The verification confirmed Modelo 036 loads from the directory-fragment
layout with the same census revision metadata, profile binding, casillas,
workbook parity reference, verification expectation, application links,
event-triggered filing schedule, declaration-PDF extraction profile,
construct membership, and completeness manifest.

Reviewability baseline after the split:

- `036.toml` no longer exists.
- Modelo 036 has 11 TOML fragments.
- Largest Modelo 036 fragment: 56 lines (`application_links`).
- No Modelo 036 fragment exceeds the reviewability ceiling.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_036_registry.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_parser_extracts_modelo_036_synthetic_fixture_targets -q`
- Result: 88 passed in 205.58 s.
