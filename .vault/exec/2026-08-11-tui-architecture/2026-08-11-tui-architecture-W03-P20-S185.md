---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:fe0040c12551fc67a219b9c12494dcbd360864ba089058d8c6563f97bff69e95'
step_id: 'S185'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Delete the dedicated constructs family after eliminating every definition, test, documentation, and import

## Scope

- `src/cadrumo/domain/calculations/registry/constructs.py`

## Changes

D src/cadrumo/domain/calculations/registry/constructs.py
M src/cadrumo/domain/calculations/registry/tests/test_modelo_100_registry_constructs.py
M src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py
M dev/quality/registry_facade_family_census.py
M dev/quality/registry_facade_family_census.v1.json
M dev/tests/test_registry_facade_family_census.py
D docs/api/cadrumo.domain.calculations.registry.constructs.rst
M docs/api/cadrumo.domain.calculations.registry.rst

## Notes

The reader had no production caller. The census recorded one, but that module
does not import it. Registry build already resolves construct members through
`validate_construct_closure`, which checks member existence and the legal- and
source-ref coverage the grounding rule requires, so the reader duplicated that
work for callers that do not exist.

Three of its tests existed only to drive the reader, including a runtime
defence-in-depth check whose own docstring records that the pre-flight
validator normally catches the case. With no caller, that runtime gate guarded
nothing; the validator's own tests remain and are the real protection.

The remaining tests assert registry data rather than reader behaviour. They now
read the construct definitions directly, driven by the validator's kind-to-field
mapping rather than a copy of it, so a new member kind reaches them as soon as
production learns it.

The census had no representation for an outright deletion: every row was
assumed to have a current defining site, and five sites raised when it was
absent. Those now skip locator and span resolution for a row adjudicated
`delete` and whose path is genuinely gone. The guard is keyed on the
disposition rather than on mere absence, so an accidental deletion anywhere
else still reds.
