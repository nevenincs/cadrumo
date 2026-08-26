---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6ac1827d3344d4bb92eb45c0788f55e4e2b6d6f67b29e6a61ea686865acc919e'
step_id: 'S247'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Privatize the validate implementation after eliminating every external consumer and public package reach

## Scope

- `src/cadrumo/domain/calculations/registry/validate.py`

## Changes

R src/cadrumo/domain/calculations/registry/validate.py -> _validate.py
R src/cadrumo/application/modelo/tests/test_modelo_303_verification_source_snapshot_resolution.py -> domain/calculations/registry/tests/
M 24 registry modules and tests repointed onto the relative private path
M dev/quality/registry_facade_family_census.v1.json
D docs/api/cadrumo.domain.calculations.registry.validate.rst
M docs/api/cadrumo.domain.calculations.registry.rst

## Notes

The row asks for privatisation after eliminating every external consumer. There
was exactly one: a test in the application tree constructing `RegistryValidator`
to assert a registry validation refusal. Every import in that file resolved to
the registry or to core, so it was misplaced rather than a genuine cross-package
contract. It moved to the registry's own tests, which eliminates the reach and
puts the file at its owning boundary; deleting it would have dropped a real
refusal assertion.

The public-API gate caught the failure mode this rename invites: repointing
consumers while preserving their absolute import form turns each one into an
absolute import of a private module. Twenty-four files now name the module
relatively.

The census row was re-adjudicated onto the private path and refreshed, and the
row left the fixed-point gate's outstanding table because its terminal state is
now reached.
