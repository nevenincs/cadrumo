---
tags:
  - '#audit'
  - '#registry-authority-flow'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-registry-authority-flow-plan]]"
---



# `registry-authority-flow` audit: registry authority flow inventory

## Scope

Wave W01 inventory for the registry authority rollout. The scan covered direct
use of raw registry loader functions across `src/aeat`, then classified each
hit as compiler internals, authority internals, barrel exports, tests, or
production orchestration debt.

## Findings

REGISTRY-AUTH-FLOW-001 | HIGH | Production raw-loader orchestration exists outside the authority
Direct `load_registry_tree` production callers were found in
`src/aeat/adapters/outbound/aeat/sede/_declarations.py`,
`src/aeat/application/registry/__init__.py`, and
`src/aeat/entrypoints/cli/_config/_google.py`. These are migration targets for
Wave W03 because they compile the registry directly instead of entering through
`ValidatedRegistryAuthority`.

REGISTRY-AUTH-FLOW-002 | MEDIUM | Registry-internal helpers still bypass the authority
`src/aeat/domain/calculations/registry/_formula_runtime.py` and
`src/aeat/domain/calculations/registry/_scenarios.py` call `load_registry_tree`
directly. These need explicit classification before enforcement: either
convert them to authority-backed helpers or allow them as compiler-adjacent
tooling with a documented reason.

REGISTRY-AUTH-FLOW-003 | MEDIUM | Cycle-safe legal-parameter loaders are a separate allowed path
`src/aeat/core/resources/_repos/legal_parameters.py`,
`src/aeat/domain/fincas/_imputacion_parameters.py`, and
`src/aeat/domain/iva/_recargo_equivalencia.py` use
`load_legal_parameters_only`. The implementation comments explain this avoids
a circular import through full registry binding loading. This should remain an
allowlisted narrow catalogue path unless a later authority design provides an
equally cycle-safe parameter surface.

REGISTRY-AUTH-FLOW-004 | LOW | Raw loader exports remain public through package barrels
`src/aeat/domain/calculations/__init__.py` and
`src/aeat/domain/calculations/registry/__init__.py` export raw loader
functions. Tests and compiler tooling rely on this today. Production import
guards should restrict production use before deciding whether to remove public
exports.

REGISTRY-AUTH-FLOW-005 | LOW | Test usage is broad but mostly legitimate
Most direct loader usage is in registry tests. That is acceptable for compiler,
schema, catalogue, drift, and committed-registry tests. Production boundary
tests should distinguish those from application or adapter orchestration tests.

## Recommendations

Use the following Wave W01 allowlist categories:

- compiler internals: `_loader.py`;
- authority internals: `_authority.py`;
- public barrel exports: `registry/__init__.py` and `domain/calculations/__init__.py`;
- compiler and schema tests: test modules under `domain/calculations/registry`;
- cycle-safe legal parameter path: `load_legal_parameters_only` users;
- migration debt: Sede declarations, application registry service, and Google
  config commands.

Wave W02 should fix cache invalidation and nested export identity before Wave
W03 migrates production call sites. Wave W04 should then encode the allowlist in
`test_public_api_boundaries.py`.
