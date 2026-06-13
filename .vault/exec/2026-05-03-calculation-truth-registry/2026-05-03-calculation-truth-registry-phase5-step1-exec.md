---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step1`

Hard-cut legacy calculation, hydrate, schema-write, filing, verification,
ledger, and export-generation authorities from filing-grade runtime paths.

- Modified: `src/aeat/domain/schema/_cache.py`
- Modified: `src/aeat/domain/casillas/catalogue.py`
- Modified: `src/aeat/domain/casillas/_hydrate/__init__.py`
- Modified: `src/aeat/application/filing/_export.py`
- Modified: `src/aeat/application/filing/_review.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Modified: `src/aeat/application/verification/_verify.py`
- Modified: `src/aeat/domain/calculations/_registry.py`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `src/aeat/entrypoints/cli/audit/__init__.py`
- Modified: `src/aeat/entrypoints/cli/data/ledgers/assets.py`
- Modified: `src/aeat/entrypoints/cli/data/ledgers/anexo_d.py`
- Modified: `src/aeat/domain/profile/__init__.py`
- Modified: `src/aeat/domain/profile/assets/__init__.py`
- Modified: `src/aeat/domain/profile/inventory/__init__.py`
- Modified: `src/aeat/application/aggregation/_models.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/_generate.py`
- Created: `tests/import_contract/test_registry_deletion_gates.py`
- Deleted: internal `src/aeat/domain/casillas/_hydrate/` generation modules

## Description

This checkpoint removes runtime access to the old authorities that could still
calculate, write, generate, or project legal-rule truth outside validated
registry snapshots.

Schema cache writes and casilla catalogue writes now fail closed. The app-facing
hydrate surface is disabled and its internal generation modules are deleted.
Application filing, filing review, verification, filing CLI, audit CLI, data
ledger commands, profile amortization helpers, aggregation models, the legacy
calculation registry facade, and the export module generator now stop at the
registry-snapshot boundary instead of importing old rulesets, filing builders,
generated export modules, or hydrate writers.

Import-contract tests enforce the new boundary so these public paths cannot
silently fall back to old formula, hydrate, generated-layout, or write surfaces.

## Tests

Verified the checkpoint with targeted real-behaviour tests covering schema and
casilla write refusal, hydrate deletion gates, filing/export/review failure
paths, verification refusal, CLI refusal, aggregation/profile decoupling,
legacy registry facade refusal, and generated export module refusal.

The broad touched test run passed with 164 tests. `ty check` passed. Targeted
`ruff check` on changed surfaces passed. Full `ruff check` still reports
pre-existing unrelated baseline violations outside this checkpoint.
