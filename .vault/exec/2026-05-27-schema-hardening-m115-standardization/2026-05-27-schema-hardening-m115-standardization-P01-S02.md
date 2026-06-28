---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m115-standardization-plan]]'
---

# `schema-hardening-m115-standardization` `P01.S02`

Mechanically split M115 into the generic directory-fragment layout.

- Deleted: `src/aeat/_data/registry/aeat/modelos/115.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/115/manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/115/revisions/2019-y-siguientes/revision.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/115/revisions/2019-y-siguientes`

## Description

The split preserved M115 line content in source order across 14 TOML fragments:
one manifest, one revision manifest, and 12 section fragments. No ids, labels,
semantic roles, formulas, export offsets, application links, deadline windows,
citations, or schema fields were changed during the move.

The reconstructed fragment stream is line-identical to the committed
single-file source.

Post-split baseline:

- M115 has one fragment-directory revision source.
- M115 has no `115.toml` single-file source.
- Largest M115 TOML fragment: 525 lines.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_115_registry.py src/aeat/domain/calculations/registry/test_modelo_115_round_trip.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `25 passed in 76.00s`
