---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m347-standardization-plan]]'
---



# `schema-hardening-m347-standardization` `P01.S04`

Records the Modelo 347 standardization review outcome, the post-split
reviewability baseline, and the next single-file normalization edge.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m347-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m347-standardization/2026-05-27-schema-hardening-m347-standardization-P01-S04.md`

## Description

The S01 inventory mapped the M347 single-file source into an 11-fragment
directory layout matching the established generic loader contract. The S02
mechanical split landed `manifest.toml` plus the
`revisions/2008-y-siguientes/` fragment tree without altering any casilla,
parameter, reference, schedule, extraction-profile, or construct content.
The S03 verification confirmed directory loading, registry validity,
annual deadline resolution, parser fixture extraction, and stale-sibling
guard coverage.

Post-split reviewability baseline: 11 TOML fragments, largest 81 lines
(`deadline_windows`), no fragment over the per-fragment reviewability
ceiling. The original `347.toml` is removed; the fragment tree is the
canonical M347 source.

The remaining root-level single-file modelos are `309.toml` (330 lines),
`360.toml` (292), `036.toml` (284), `840.toml` (196), and `308.toml`
(181). `309.toml` is the largest remaining root-level single-file modelo
and is therefore the next standardization edge.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_347_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/deadlines/test_engine.py::TestAnnualFilingWindows::test_modelo_347_annual_window_resolves src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_parser_extracts_modelo_347_synthetic_fixture_targets -q`
- Result: covered by the S03 verification pass (39 passed).
