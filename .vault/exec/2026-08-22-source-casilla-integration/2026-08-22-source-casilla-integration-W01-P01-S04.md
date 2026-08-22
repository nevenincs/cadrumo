---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:a5fcd867e96c137d948f29a762b75a18c1a35361cae8853d9f8a16c054b089c2'
step_id: 'S04'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# expose the canonical connectivity models through the core public surface

## Scope

- `src/cadrumo/core/__init__.py`

## Description

- Read the core lazy-facade ownership and ordering conventions.
- Publish every reviewed source-connectivity contract name through core `__all__`.
- Map each public name to its sole owning `source_connectivity` module through the existing lazy loader.
- Verify public imports resolve to the exact owner objects with no duplicate export names.

## Outcome

All canonical source-connectivity identities, dispositions, evidence records,
proof contracts, expiry and follow-up types, and the live proof-authority protocol
are importable from `cadrumo.core`. Cross-package consumers no longer need to
reach into the owning module, and lazy import behavior is preserved.

## Notes

Ruff and module compilation passed. Focused import assertions proved every owner
export is present in `core.__all__`, visible through `dir(core)`, resolves to the
same object as its canonical definition, and appears exactly once. The initial
probe incorrectly assumed the entire legacy facade is globally alphabetized;
the facade instead groups constants before classes, while the added connectivity
class group itself follows the existing alphabetical convention.

The four production facade/import-hygiene gates relevant to this change passed.
The whole import-hygiene module remains red because concurrent test-only private
imports exceed the separately maintained test-debt baseline (`110` current
versus `69` documented); this facade introduces none of those sites and the
production hard-zero and underscore-export gates are green.
