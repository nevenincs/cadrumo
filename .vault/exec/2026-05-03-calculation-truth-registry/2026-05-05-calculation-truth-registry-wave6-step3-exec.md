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



# `calculation-truth-registry` `Wave 6` `Modelo 180 perceptor coverage`

Expanded Modelo 180 submitted-file coverage and closed annual-summary
dependency classifications required by the central registry validator.

- Modified: `registry/aeat/modelos/180.toml`
- Modified: `registry/aeat/modelos/190.toml`
- Modified: `registry/aeat/modelos/193.toml`
- Modified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Modelo 180 now declares additional type 2 perceptor fixed-width fields from
the official record design for both covered revisions: NIF, name, province,
modality, retention percentage, accrual year, property situation, cadastral
reference, property province, and property postal code. The submitted-file
extraction profiles include those casillas, and the committed parser test now
loads the same fields from the synthetic fixed-width record.

The Modelo 180 annual-summary construct now classifies Modelo 115 as its direct
annual-settlement source and covers every Modelo 115 relation. Whole-tree
verification also required the same closure for existing Modelo 190 and Modelo
193 annual-summary relation sets, so those modelos now classify their Modelo
111 and Modelo 123 dependencies respectively.

The CLI registry command is wired under `aeat app registry` so the registry
verification gate remains directly executable through the application CLI.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_committed_registry.py::test_committed_modelo_180_record_design_parses_declarante_and_perceptor_records -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_relation_closure.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q`
- `uv run aeat app registry verify --registry-root registry/aeat --source-root . --json`
- `uv run ruff check src/aeat/entrypoints/cli/__init__.py src/aeat/domain/calculations/registry/test_committed_registry.py`
