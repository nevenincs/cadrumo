---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m190-standardization-plan]]'
---

# `schema-hardening-m190-standardization` `P01.S02`

Mechanically split M190 into the generic directory-fragment layout.

- Deleted: `src/aeat/_data/registry/aeat/modelos/190.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/190/manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/190/revisions/2024-y-siguientes/revision.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/190/revisions/2024-y-siguientes`

## Description

The split preserved M190 line content in source order across 15 TOML fragments:
one manifest, one revision manifest, and 13 section fragments. The original
two non-contiguous `bindings` blocks remain separate ordered fragments. No ids,
labels, semantic roles, formulas, relations, application links, citations, or
schema fields were changed during the move.

The reconstructed fragment stream is line-identical to the committed
single-file source. The byte hash differs only because the committed object and
Windows worktree use different line endings.

Post-split baseline:

- M190 has one fragment-directory revision source.
- M190 has no `190.toml` single-file source.
- Largest M190 TOML fragment: 285 lines.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_190_registry.py src/aeat/domain/calculations/registry/test_modelo_190_193_round_trip.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `27 passed in 83.81s`
