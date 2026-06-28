---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
---



# `schema-hardening` `P01.S02`

Added generic fragment-loader support for revision-level continuity evolution
records.

- Modified: `src/aeat/domain/calculations/registry/_loader.py`
- Modified: `src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p01-s02-review.md`

## Description

Registered `casilla_continuidad_evolutions` with the revision append-array
merge path used by other schema-owned revision arrays. This keeps fragmented
revision directories generic: continuity evolution declarations can live in
their own TOML fragments without modelo-specific loader branches.

Extended the fragmented revision round-trip test with two continuity evolution
fragments. The test compares the fragmented directory object with an equivalent
single-file modelo, so a scalar merge regression or missing append-array
registration would fail at load time.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_loader.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
