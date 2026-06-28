---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m347-standardization-plan]]'
---



# `schema-hardening-m347-standardization` `P01.S03`

Verified the Modelo 347 directory-fragment layout against the focused
registry, loader, deadline, and parser-fixture surfaces.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m347-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m347-standardization/2026-05-27-schema-hardening-m347-standardization-P01-S03.md`

## Description

The verification confirmed Modelo 347 loads from the directory-fragment
layout with the same casillas, static threshold parameter, workbook parity
references, live cross-reference guard surfaces, application links,
annual filing schedule, February annual deadline windows, declaration-PDF
extraction profile, and construct membership.

Reviewability baseline after the split:

- `347.toml` no longer exists.
- Modelo 347 has 11 TOML fragments.
- Largest Modelo 347 fragment: 81 lines (`deadline_windows`).
- No Modelo 347 fragment exceeds the reviewability ceiling.

## Tests

Initial gate attempt:

- `uv run --no-sync pytest ... test_engine.py::TestDeadlineEngine::test_modelo_347_annual_window_resolves ... -q`
- Result: failed before running the intended suite because
  `TestDeadlineEngine::test_modelo_347_annual_window_resolves` is not a
  valid node id in the current checkout.

Corrected gate:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_347_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/deadlines/test_engine.py::TestAnnualFilingWindows::test_modelo_347_annual_window_resolves src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_parser_extracts_modelo_347_synthetic_fixture_targets -q`
- Result: 39 passed in 168.57 s.
