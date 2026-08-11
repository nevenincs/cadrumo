---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:d73a94f1d7129f95be09b70e36b5eb2c121ce7bc94c6190c08350d71899a0986'
step_id: 'S11'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Centralize registry relations by target binding

## Scope

- `src/cadrumo/domain/calculations/registry/_queries.py`
- `src/cadrumo/domain/calculations/registry/__init__.py`
- `src/cadrumo/domain/calculations/registry/tests/test_queries.py`
- `src/cadrumo/application/calculations/_relation_prefill.py`

## Description

- Add the ordered `relations_by_target_binding` derivation to the registry query authority and export it through the public registry facade.
- Retarget the relation-input projection and operator-input requirement query paths to the canonical grouping.
- Retarget the M202 relation-prefill zero-default path to the same grouping without changing its period, kind, or source rules.
- Prove declaration order against the real bundled M202 revision and run focused domain, application, integration, static, structural, collection, and review gates.

## Outcome

- The three governed target-binding grouping loops now have one canonical public owner.
- The real M202 grouping, first-period zero, second-period unresolved, and CLI relation-input behaviors pass.
- Formal review reported PASS with no findings.

## Notes

- The broader registry-query lane ran 25 tests with two unrelated failures: both stop on missing Spanish localization key `modelo.schema.303.revision.2026-y-siguientes.casilla.500.label` before relation grouping is exercised.
- `ModeloRevision.producer_inventory` remains a distinct producer-inventory grain explicitly left untouched by the accepted canonical-derivations ADR.
