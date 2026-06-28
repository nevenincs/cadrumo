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



# `calculation-truth-registry` `Wave 6` `Modelo 180 representative NIF`

Closed the remaining official type 2 identity slot for Modelo 180 submitted
files.

- Modified: `registry/aeat/modelos/180.toml`
- Modified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Modelo 180 now declares the optional legal representative NIF at type 2
positions 27 through 35 for both supported revisions. The field is represented
as a registry casilla, bound to an export-layout field, and included in the
submitted-file extraction targets.

The committed fixed-width parser test writes this field into the synthetic
perceptor record and verifies that it is parsed through the central registry
layout.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_committed_registry.py::test_committed_modelo_180_record_design_parses_declarante_and_perceptor_records -q`
- `uv run aeat app registry verify --registry-root registry/aeat --source-root . --json`
