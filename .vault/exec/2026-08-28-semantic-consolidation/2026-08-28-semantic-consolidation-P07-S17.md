---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:2e4ab3f991b87632c86f75a8fd950f60673b47026411189e1e12057c8591b03d'
step_id: 'S17'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Relocate the production code out of the four namespaces that are modules in disguise before their namespaces can be made inert

## Scope

- `src/cadrumo/`

## Changes

- `verify:` no namespace remaining in the tree is a package whose only file is `__init__.py`
- `verify:` the four relocations that closed this population are recorded under `P07.S164`

## Notes

Closed by the relocations recorded under `P07.S164`: `core/money` to
`rounding.py`, `domain/notifications` to `sancion.py`,
`application/bienes_inversion` and `application/prorrata_register` to
`_service.py`. Each was a package containing nothing but an `__init__.py` that
held a real class -- the namespace doing the work a named module should.

Verified by re-deriving the population rather than by counting off the four:
every namespace that still defines production code directly has sibling modules,
so none is a module in disguise. The step's population is empty, not merely
reduced by four.

Two of the four landed on `_service.py`, which their consumers reach from other
packages. That is a cross-package private import, and it is carried as its own
finding in
`2026-08-31-semantic-consolidation-private-module-cross-package-debt-audit`
rather than left implicit here: the relocation this step asked for is done, and
the naming of two of its results is part of a wider open question.
