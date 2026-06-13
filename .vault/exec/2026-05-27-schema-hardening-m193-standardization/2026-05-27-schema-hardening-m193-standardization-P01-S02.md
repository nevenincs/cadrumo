---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m193-standardization-plan]]'
---



# `schema-hardening-m193-standardization` `P01.S02`

Mechanically split Modelo 193 from single-file TOML into the generic
directory/fragments layout.

- Deleted: `src/aeat/_data/registry/aeat/modelos/193.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/193/manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/193/revisions/2024-y-siguientes/revision.toml`
- Created: 13 ordered revision section fragments under `src/aeat/_data/registry/aeat/modelos/193/revisions/2024-y-siguientes`
- Created: `.vault/exec/2026-05-27-schema-hardening-m193-standardization/2026-05-27-schema-hardening-m193-standardization-P01-S02.md`

## Description

The split preserves source order and content from the committed `193.toml`
without normalizing schema fields. The manifest carries only `[modelo]`.
Revision metadata is isolated in `revision.toml`. The remaining revision
tables are ordered fragments for summary bindings, relations, casillas,
formulas, extraction profiles, live cross references, workbook parity refs,
verification expectations, application links, row-producer bindings,
constructs, dependency classifications, and completeness manifest data.

The reconstructed fragment stream matched the committed source text exactly
across 15 generated TOML files before the stale single-file sibling was
removed.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_193_registry.py src/aeat/domain/calculations/registry/test_modelo_190_193_round_trip.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- Result: 27 passed.
