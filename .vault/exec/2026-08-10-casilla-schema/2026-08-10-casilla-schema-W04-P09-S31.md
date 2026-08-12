---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:5b677827b3c0efd0b3ff2faf260893e11c466d0df7e0358bf59977039fcb3f38'
step_id: 'S31'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Delete the strict bound-input resolver

## Scope

- `src/cadrumo/domain/calculations/registry/`
- Direct resolver consumers and structural regression tests.

## Description

- Delete the strict registry bound-input resolver and its implementation-module export.
- Remove the resolver import and public-name entry from the registry package facade.
- Retarget calculation, continuity, worked-example, and scenario setup onto the living application projector.
- Remove stale strict-resolver references from application documentation, registry validation prose, and migrated test narratives.
- Add a filesystem-AST structural regression over production Python sources without importing a private domain module.

## Outcome

`resolve_available_bound_inputs_by_casilla_id` remains the sole production resolver definition and the public application facade exports it. The strict resolver has zero production definitions, imports, facade bindings, or `__all__` entries; no alias or compatibility shim remains. The exact retired identifier occurs once under `src`, deliberately in the structural test's explicit absence assertion. Unresolved-input authority remains on the existing advisory and verification paths.

Focused Ruff and BasedPyright checks passed. The structural resolver-surface regression passed serially. A serial real-registry/application selection produced nine passes and one profile-fixture failure before reaching the resolver path because `iva.m303_regime_composition` was not explicitly declared. An earlier parallel selection was invalidated by concurrent registry writes: 18 tests passed, while the remaining cases reported the registry fingerprint-churn refusal.

## Notes

No production registry data or peer-owned dirty path was edited. The registry-authority test lane was retried serially after the concurrent-write collision; the remaining failure is outside the deleted resolver surface and is recorded rather than hidden.
