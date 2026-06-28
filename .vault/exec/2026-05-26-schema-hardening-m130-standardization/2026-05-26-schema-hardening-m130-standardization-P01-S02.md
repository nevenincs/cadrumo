---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S02'
related:
  - '[[2026-05-26-schema-hardening-m130-standardization-plan]]'
---

# `schema-hardening-m130-standardization` `P01.S02`

Mechanically split Modelo 130 from single-file layout into generic
directory/fragments layout.

- Modified: `src/aeat/_data/registry/aeat/modelos/130.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/130`

## Description

The single `130.toml` file was replaced by `130/manifest.toml` and one
revision fragment directory at `130/revisions/2019-y-siguientes`.

The split preserved the existing TOML order by moving each contiguous revision
section run into a numbered section fragment. Repeated binding and formula runs
remain separate fragment files. No loader, schema, or per-modelo definition
code changed.

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_130_registry.py -q`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
