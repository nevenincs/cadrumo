---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `Wave 6` `Modelo 180 address block`

Completed the committed Modelo 180 submitted-file address block for the
official type 2 perceptor record.

- Modified: `registry/aeat/modelos/180.toml`
- Modified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Modelo 180 now declares the official inmueble address positions 135 through
320 for both supported revisions. The registry includes casillas, export
field bindings, and extraction targets for street type, street name, numbering
type, house number, number qualifier, block, portal, stairs, floor, door,
address complement, locality, municipality, and municipality code.

The committed fixed-width parser test writes those fields into the synthetic
type 2 record and verifies that the registry parser reads them back through
the central layout. The `aeat app registry` entrypoint was restored in the
current worktree so the verification command remains callable.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_committed_registry.py::test_committed_modelo_180_record_design_parses_declarante_and_perceptor_records -q`
- `uv run aeat app registry verify --registry-root registry/aeat --source-root . --json`
