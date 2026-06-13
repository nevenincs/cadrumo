---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m390-standardization-plan]]'
---

# `schema-hardening-m390-standardization` `P01.S02`

Mechanically split M390 into the generic directory-fragment layout.

- Deleted: `src/aeat/_data/registry/aeat/modelos/390.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/390/manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/revision.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes`

## Description

The split preserved M390 line content in source order across 15 TOML fragments:
one manifest, one revision manifest, and 13 section fragments. The original
two non-contiguous `casillas` blocks remain separate ordered fragments. No ids,
labels, semantic roles, formulas, filing schedules, deadline windows,
application links, citations, or schema fields were changed during the move.

The reconstructed fragment stream is line-identical to the committed
single-file source.

Post-split baseline:

- M390 has one fragment-directory revision source.
- M390 has no `390.toml` single-file source.
- Largest M390 TOML fragment: 182 lines.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `35 passed in 84.79s`
