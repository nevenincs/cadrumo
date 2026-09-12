---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:d5f786abe6a4626450ade2accb15322c4166bfffd93dcbff3732575185179c45'
step_id: 'S24'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Make the inventory resolver emit CalculationSourceProvenance for every row binding it produces, with terminal_origin detail_record, source_ref and fingerprint, so its filing-grade rows pass the terminal-origin audit

## Scope

- `src/cadrumo/application/aggregation/inventory.py`
- `src/cadrumo/application/aggregation/tests/`

## Changes

- `M` `src/cadrumo/application/aggregation/inventory.py`
- `M` `src/cadrumo/application/aggregation/tests/test_inventory_source.py`
- `verify:` `uv run ruff check src/cadrumo/application/aggregation/inventory.py src/cadrumo/application/aggregation/tests/test_inventory_source.py` -> `fail`
- `verify:` `uv run ty check src/cadrumo/application/aggregation/inventory.py src/cadrumo/application/aggregation/tests/test_inventory_source.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/aggregation/inventory.py src/cadrumo/application/aggregation/tests/test_inventory_source.py` -> `pass`
- `verify:` `uv run pytest src/cadrumo/application/aggregation/tests/test_inventory_source.py -n 0` -> `fail`

## Notes

The three ruff findings are pre-existing missing-docstring errors on untouched
lines; the identical three reproduce against the committed file.

The bundled authority artifact is mid-republish and does not decode, so pytest
errors at the autouse authority fixture for every test in the file and the
inventory projection itself cannot be computed. The new empty-rows test and the
provenance/audit join were verified by direct execution instead; the new
multi-row test remains unexecuted until the artifact republishes.

The shared `_binding` and `_revision` helpers in the test module are stale
against the current `InventoryProvider` (they still pass a removed
`filing_year` key), so the new tests build their own row templates and revision
rather than rewriting another contributor's in-flight helpers.
