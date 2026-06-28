---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m036-standardization-plan]]'
---



# `schema-hardening-m036-standardization` `P01.S04`

Records the Modelo 036 standardization review outcome, the post-split
reviewability baseline, and the next single-file normalization edge.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m036-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m036-standardization/2026-05-27-schema-hardening-m036-standardization-P01-S04.md`

## Description

The S01 inventory mapped the M036 single-file source into an 11-fragment
directory layout matching the established generic loader contract. The S02
mechanical split landed `manifest.toml` plus the
`revisions/2025-02-03-y-siguientes/` fragment tree without altering any
binding, casilla, reference, verification expectation, application link,
schedule, extraction profile, construct, or completeness-manifest content.
The S03 verification confirmed directory loading, registry validity, census
foundation behavior, event-period query behavior, and parser fixture behavior.

Post-split reviewability baseline: 11 TOML fragments, largest 56 lines
(`application_links`), no fragment over the per-fragment reviewability
ceiling. The original `036.toml` is removed; the fragment tree is the
canonical M036 source.

The remaining root-level single-file modelos are `840.toml` and `308.toml`.
`840.toml` is the largest remaining root-level single-file modelo and is
therefore the next standardization edge.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_036_registry.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/adapters/inbound/declaracion/test_parser_boundary.py::test_parser_extracts_modelo_036_synthetic_fixture_targets -q`
- Result: covered by the S03 verification pass (88 passed).
