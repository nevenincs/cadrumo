---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m360-standardization-plan]]'
---



# `schema-hardening-m360-standardization` `P01.S04`

Records the Modelo 360 standardization review outcome, the post-split
reviewability baseline, and the next single-file normalization edge.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m360-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m360-standardization/2026-05-27-schema-hardening-m360-standardization-P01-S04.md`

## Description

The S01 inventory mapped the M360 single-file source into an 11-fragment
directory layout matching the established generic loader contract. The S02
mechanical split landed `manifest.toml` plus the
`revisions/2010-y-siguientes/` fragment tree without altering any casilla,
parameter, reference, schedule, deadline, row-binding, or construct content.
The S03 verification confirmed directory loading, registry validity, deadline
behavior, refund-operation row resolution, model coverage, row assembly, and
round-trip behavior.

Post-split reviewability baseline: 11 TOML fragments, largest 55 lines
(`bindings`), no fragment over the per-fragment reviewability ceiling. The
original `360.toml` is removed; the fragment tree is the canonical M360
source.

The remaining root-level single-file modelos are `036.toml`, `840.toml`,
and `308.toml`. `036.toml` is the largest remaining root-level single-file
modelo and is therefore the next standardization edge, subject to a scoped
pre-edit diff check because previous shared-worktree work touched M036.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_360_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_detail_record_row_builders.py::test_resolve_refund_binding_row_values_sorts_by_member_state_date_supplier src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py src/aeat/application/calculations/test_row_set_assembly.py::test_assemble_refund_parses_iso_operation_date src/aeat/application/calculations/test_detail_record_round_trip.py::test_modelo_360_refund_round_trip_preserves_member_state_and_dates -q`
- Result: covered by the S03 verification pass (47 passed).
