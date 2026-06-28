---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m720-standardization-plan]]'
---

# `schema-hardening-m720-standardization` `P01.S02`

Mechanically split M720 into the generic directory-fragment layout.

- Deleted: `src/aeat/_data/registry/aeat/modelos/720.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/720/manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/revision.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes`

## Description

The split preserved M720 line content in source order across 16 TOML fragments:
one manifest, one revision manifest, and 14 section fragments. The original
two non-contiguous `bindings` blocks remain separate ordered fragments. No ids,
labels, semantic roles, export layout records, filing schedules, deadline
windows, application links, citations, or schema fields were changed during the
move.

The reconstructed fragment stream is line-identical to the committed
single-file source.

Post-split baseline:

- M720 has one fragment-directory revision source.
- M720 has no `720.toml` single-file source.
- Largest M720 TOML fragment: 301 lines.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_720_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- `43 passed in 88.14s`
