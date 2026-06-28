---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step3`

Removed disabled legal-rule writer functions from public package surfaces.

- Modified: `src/aeat/domain/casillas/__init__.py`
- Modified: `src/aeat/domain/casillas/_test_catalogue.py`
- Modified: `src/aeat/domain/schema/__init__.py`
- Modified: `src/aeat/domain/schema/test_cache.py`
- Modified: `tests/import_contract/test_registry_deletion_gates.py`

## Description

`save_casillas` and `save_modelo_to_cache` remain private, fail-closed
compatibility functions inside their implementation modules so tests can prove
they do not write. They are no longer exported from `aeat.domain.casillas` or
`aeat.domain.schema`, preventing normal consumers from discovering them as
supported package APIs.

The import-contract tests now assert that the disabled writer names do not
appear in the package `__init__` public surfaces.

## Tests

Verified with targeted `ruff check`, `ty check`, and a focused test slice:
`src/aeat/domain/casillas/_test_catalogue.py`,
`src/aeat/domain/schema/test_cache.py`, and
`tests/import_contract/test_registry_deletion_gates.py`. The slice passed 36
tests.
