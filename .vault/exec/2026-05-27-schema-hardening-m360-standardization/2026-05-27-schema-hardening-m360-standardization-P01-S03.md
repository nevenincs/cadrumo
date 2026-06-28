---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m360-standardization-plan]]'
---



# `schema-hardening-m360-standardization` `P01.S03`

Verified the Modelo 360 directory-fragment layout against the focused
registry, loader, deadline, refund row-builder, model coverage, row assembly,
and round-trip surfaces.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m360-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m360-standardization/2026-05-27-schema-hardening-m360-standardization-P01-S03.md`

## Description

The verification confirmed Modelo 360 loads from the directory-fragment
layout with the same ad-hoc revision metadata, workbook parity reference,
casillas, static refund thresholds, live cross-reference guard surfaces,
application links, filing schedule, deadline windows, refund-operation
row bindings, and construct membership.

Reviewability baseline after the split:

- `360.toml` no longer exists.
- Modelo 360 has 11 TOML fragments.
- Largest Modelo 360 fragment: 55 lines (`bindings`).
- No Modelo 360 fragment exceeds the reviewability ceiling.

## Tests

Initial gate attempt:

- `uv run --no-sync pytest ... test_row_set_assembly.py::test_detail_record_row_set_assembles_modelo_360_refund_operations ... -q`
- Result: failed before running the intended suite because the selected
  row-set test node id is not present in the current checkout.

Corrected gate:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_360_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_detail_record_row_builders.py::test_resolve_refund_binding_row_values_sorts_by_member_state_date_supplier src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py src/aeat/application/calculations/test_row_set_assembly.py::test_assemble_refund_parses_iso_operation_date src/aeat/application/calculations/test_detail_record_round_trip.py::test_modelo_360_refund_round_trip_preserves_member_state_and_dates -q`
- Result: 47 passed in 188.90 s.
