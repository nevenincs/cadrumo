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



# `calculation-truth-registry` `Renta` `dependency classification gate`

Hardened the central registry validator so Modelo 100 cannot validate with
unclassified, partially classified, or multiply classified relation sources.

- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The validator now builds the inverse relation-source ledger for each revision.
Every relation source must have exactly one dependency classification, that
classification cannot be `non_dependency`, and it must cover every relation
declared for the source modelo. This hardens Modelo 100 Renta dependency
resolution before additional subdomain formulas and observation bindings are
added.

The tests mutate the loaded Modelo 100 registry objects directly and verify
hard failures for a missing source classification, partial relation coverage,
and duplicate source classification.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_validator_rejects_unclassified_relation_source src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_validator_rejects_partial_dependency_classification_relation_coverage src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_validator_rejects_duplicate_dependency_classification_source -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_100_registry.py -q`
- `uv run aeat app registry verify --registry-root registry/aeat --source-root . --json`
- `uv run ruff check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- `uv run ty check src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
