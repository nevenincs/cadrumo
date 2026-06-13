---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S140'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P20.S140 Modelo CLI command-group split

Scope:
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/_modelo_export_cli.py`
- `src/aeat/entrypoints/cli/test_modelo_export_verb.py`

## Description

Split the root-level modelo export command out of the monolithic modelo CLI module into a bounded command registration module without changing the public command name or operator-facing command surface.

## Changes

- Added `_modelo_export_cli.py` as the Typer registration module for the root-level `aeat app modelo export` command.
- Moved the export command body and Typer option declarations from `_modelo.py` into `register_export_commands`.
- Kept `_modelo.py` responsible for wiring the root Typer app and passing existing shared resolver/refusal helpers into the export registration module.
- Preserved raw revision-id escape-hatch compatibility and natural-key selector resolution by continuing to call `_resolve_revision_for_cli(..., default_for="export")`.
- Preserved existing export refusal translation, active bucket/profile loading, output-path requirement, envelope emission, and localized result messages.

## Verification

- `uv run --no-sync python -m py_compile src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_export_cli.py` - passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/_modelo_export_cli.py src/aeat/entrypoints/cli/test_modelo_export_verb.py` - passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo_export_verb.py -q` - 10 passed.
- `uv run --no-sync pytest -m docs src/aeat/entrypoints/cli/test_doc_reference_drift.py src/aeat/entrypoints/cli/test_doc_reference_conformance.py -q` - 8 passed.

## Residual

- `_modelo.py` remains large. This step created the first bounded command-group split; W06.P20.S142 owns shared helper movement, W06.P20.S143/W06.P20.S145 own static boundary and size guards, and W06.P20.S146 owns broader extracted-module regression coverage.
