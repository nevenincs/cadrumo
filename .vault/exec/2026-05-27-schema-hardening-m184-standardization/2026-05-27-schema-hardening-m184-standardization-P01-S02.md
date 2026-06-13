---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m184-standardization-plan]]'
---



# `schema-hardening-m184-standardization` `P01.S02`

Mechanically split Modelo 184 from single-file TOML into the generic
directory/fragments layout.

- Deleted: `src/aeat/_data/registry/aeat/modelos/184.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/184/manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/184/revisions/2015-y-siguientes/revision.toml`
- Created: 11 ordered revision section fragments under `src/aeat/_data/registry/aeat/modelos/184/revisions/2015-y-siguientes`
- Created: `.vault/exec/2026-05-27-schema-hardening-m184-standardization/2026-05-27-schema-hardening-m184-standardization-P01-S02.md`

## Description

The split preserves source order and content from the committed `184.toml`
without normalizing schema fields. The manifest carries only `[modelo]`.
Revision metadata is isolated in `revision.toml`. The remaining revision
tables are ordered fragments for casillas, workbook parity refs, extraction
profiles, verification expectations, live cross references, application links,
filing schedules, deadline windows, row-producer bindings, constructs, and
completeness manifest data.

The reconstructed fragment stream matched the committed source text exactly
across 13 generated TOML files before the stale single-file sibling was
removed.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_184_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- Result: 32 passed.
